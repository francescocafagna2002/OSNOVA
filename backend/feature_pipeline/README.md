# feature_pipeline

Building-level feature extraction for the Energy Fingerprints hackathon.

```
raw consumption CSVs + MP<->building mappings + hourly weather + GIGI labels
  -> feature_dataset.parquet   (one row per GP-Nr / building)
```

This package **only** computes and stores features. It does not train a
model, run SHAP, make predictions, or touch the frontend — see
`docs/superpowers/specs/2026-09-10-prediction-engine-design.md` for that
larger, separate plan (and the note in `backend/CLAUDE.md` about how the two
relate).

## Why this exists as its own package

`backend/CLAUDE.md` and the design docs describe a future `src/osnova/`
package built around **meter-year** rows (`MP ID`, one row per meter per
year). That package does not exist yet (no `src/` directory has been created
on `main`). This task's brief asks for a **building-level**, whole-history
feature table (`GP-Nr`, one row per building, no train/test year split), which
is a different entity and grain. Rather than half-implement the larger
meter-year design to satisfy a building-level spec, this is a small,
self-contained module under `backend/` that can be pointed at the real files
directly. If/when `src/osnova/` is built, its `features/` stream can import or
port the expressions here — the formulas are the same either way, only the
grouping key changes (`gp_nr` vs `meter_id, year`).

## Layout

| File | Responsibility |
| --- | --- |
| `config.py` | Every path, threshold, daypart and season boundary. Nothing below hard-codes a number. |
| `csv_utils.py` | Delimiter sniffing + accent/umlaut-tolerant column matching for the real (German-header) CSVs. |
| `mapping.py` | `MP ID -> Zählpunktbezeichnung -> GPartner`, cardinality check, `num_mp_ids` audit column. |
| `labels.py` | GIGI device columns -> `label_pv/ev/heatpump/battery`, aggregated per GP-Nr (x/-/blank -> 1/0/null). |
| `weather.py` | Per-PLZ hourly Open-Meteo frame + monthly sunny/cloudy day classification. |
| `ingest.py` | Streams each wide consumption CSV -> building-level long Parquet, checkpointed per file. |
| `timeutil.py` | Quarter-hour column parsing, daypart/season boolean columns, temperature bins. |
| `runs.py` | Generic continuous-block ("run") detection — near-zero blocks, EV threshold events, EV sessions all use this. |
| `features.py` | The battery/PV/EV/heat-pump feature expressions (vectorised polars, no per-building Python loop). |
| `sessions.py` | EV candidate-session table + its building-level aggregation (`session_*`, start/finish ratios). |
| `audit.py` | The built-in audit report (`audit_report.json` + console summary). |
| `pipeline.py` | Orchestrates all of the above into `feature_dataset.parquet`. |

## Design choices worth knowing about

- **Everything is one polars lazy pipeline**, not a per-building Python loop.
  Run/block detection (near-zero blocks, the four EV thresholds, EV sessions)
  is done with a sort + window-function run-length trick
  (`runs.add_run_columns`) so it stays vectorised and streams instead of
  materialising the whole cohort.
- **Joins do not guarantee row order.** Every `.over("gp_nr")` window
  expression (ramps, run detection) depends on `(gp_nr, ts)` order, so
  `features.prepare_frame` re-sorts immediately after the weather joins, not
  only once at the top. This was the one real bug the synthetic-data test
  caught during development (see git history) — worth remembering if you add
  another join before a window expression.
- **Multi-MP aggregation is centralised**: `config.multi_mp_strategy` (default
  `"sum"`) is interpreted in exactly one place, `ingest._apply_multi_mp_strategy`.
  Duplicate raw rows at the same `(MP ID, timestamp)` (e.g. a second
  OBIS-Code row) are collapsed the same way, `config.duplicate_mp_timestamp_strategy`.
- **`pv_presence` is `None` on purpose** — it is reserved for a future
  out-of-fold P(PV) input to the battery classifier and must never be the
  ground-truth PV label (target leakage).
- **Null vs. zero**: a ratio with zero valid intervals is `null`, not `0`;
  `session_count` legitimately is `0` when a building has no candidate
  sessions. See the `_safe_ratio` helper in `features.py`.

## Running it

From `backend/`:

```sh
python3 scripts/build_feature_dataset.py \
  --raw-consumption-dir /path/to/aew-data/test-blob/input_data \
  --mp-mapping-file "/path/to/mpid_zähler_mapping.csv" \
  --zaehler-gp-file "/path/to/Zähler-GP.csv" \
  --labels-file "/path/to/HackDays2026 - GIGI.csv" \
  --weather-dir /path/to/weather \
  --output-dir data/feature_output \
  --verbose
```

Add `--limit-buildings 100` for a fast development run, `--limit-files N` to
additionally cap how many consumption CSVs are read (dev-only — a full run
needs every file). Re-runs skip already-ingested consumption files
(`intermediate/ingest_manifest.json`) unless `--no-resume` is passed.

There is no real AEW data on a laptop (see `backend/CLAUDE.md`), so
`scripts/make_synth_fixture.py` generates a small input set in the exact real
schemas, with known devices injected, for local development and
`tests/test_feature_pipeline.py`:

```sh
python3 scripts/make_synth_fixture.py --out data/synth_input --buildings 100 --days 400
```

## Known gaps (real-data facts this could not verify locally)

- The exact weather file layout (one CSV per PLZ vs. one big file, filename
  vs. an embedded `PLZ` column) is not pinned down in the brief;
  `weather.load_weather` tries both. Confirm against the real files and adjust
  `PathsConfig.weather_glob` / `weather_plz_regex` if needed.
- The brief says OBIS-Code is unused for this task and that negative values
  already encode export directly on one channel. This is taken at face value;
  if the real files instead carry two always-positive OBIS rows (import/export
  split, as an earlier design draft assumed), `ingest.ingest_one_file`'s
  duplicate-row collapsing (sum) would silently net them to zero instead of
  the intended `import - export`. Check the real header/OBIS values first —
  see `docs/superpowers/specs/2026-09-10-prediction-engine-design.md` §2.2,
  which describes that alternative shape.
