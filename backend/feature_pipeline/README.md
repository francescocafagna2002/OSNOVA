# feature_pipeline

Building-level feature extraction for the Energy Fingerprints hackathon.

```text
raw consumption CSVs + MP<->building mappings + hourly weather + GIGI labels
  -> feature_dataset.parquet   (one row per GP-Nr / building)
```

This package **only** computes and stores features. It does not train a
model, run SHAP, make predictions, or touch the frontend — see
`docs/superpowers/specs/2026-09-10-prediction-engine-design.md` for that
larger, separate plan (and the note in `backend/CLAUDE.md` about how the two
relate).

## Team contract (2026-09-11)

This package is the team's ingest and feature engine. The entity is **one
building (`gp_nr`, Int64) over its whole observed history**, not a meter-year.
`src/osnova/` owns the downstream model, event and export stages. This package
does not change those shared contracts. The measured input facts are in
`docs/superpowers/specs/data-check-2026-09-10.md`; local validation is synthetic only.

## Layout

| File | Responsibility |
| --- | --- |
| `config.py` | Every path, threshold, daypart and season boundary. Nothing below hard-codes a number. |
| `csv_utils.py` | Delimiter sniffing + accent/umlaut-tolerant column matching for the real (German-header) CSVs. |
| `mapping.py` | `MP ID -> Zählpunktbezeichnung -> GPartner`, cardinality check, `num_mp_ids` audit column. |
| `labels.py` | GIGI device columns -> `label_pv/ev/heatpump/battery`, aggregated per GP-Nr (x/-/blank -> 1/0/null). |
| `export_labels.py` | `load_gigi_dates(labels_file)` returns nullable per-asset commissioning dates for label cleaning only. |
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
  Import and export are separate OBIS channels, never added to each other.
  The configured duplicate strategy applies only within the same MP, timestamp
  and OBIS channel. Building import, export and net power are then summed
  independently across MPs. A channel's building sum is null if an expected MP
  is absent or any contributing value is missing.
- **No PV-presence column.** The battery classifier's PV input is the
  out-of-fold `pv_prob` that `src/osnova/models/train.py` computes in its
  second stage; the ground-truth PV label is never a feature (target leakage).
- **Null vs. zero**: a ratio with zero valid intervals is `null`, not `0`;
  `session_count` legitimately is `0` when a building has no candidate
  sessions. See the `_safe_ratio` helper in `features.py`.

## Running it

From `backend/`:

```sh
uv sync
export OSNOVA_STORE_DIR=/home/renku/work/store/osnova-out
python3 scripts/build_feature_dataset.py \
  --raw-consumption-dir /home/renku/work/store/cleaned_data \
  --mp-mapping-file "/home/renku/work/aew-data/test-blob/input_data/mpid_zähler_mapping.csv" \
  --zaehler-gp-file "/home/renku/work/aew-data/test-blob/input_data/Zähler-GP.csv" \
  --labels-file "/home/renku/work/aew-data/test-blob/input_data/HackDays2026 - GIGI.csv" \
  --weather-dir /home/renku/work/store \
  --output-dir "$OSNOVA_STORE_DIR/osnova/feature_output" \
  --extra-random-gps 300 --seed 42 --limit-files 1 \
  --verbose
```

Use `uv run python` instead of `python3` if the project environment is not active.
When `--output-dir` is omitted, it defaults to
`$OSNOVA_STORE_DIR/osnova/feature_output` if the environment variable is set,
otherwise `data/feature_output`. All inputs are opened read-only.

Add `--limit-buildings 100` for a fast development run, `--limit-files N` to
additionally cap how many consumption CSVs are read (dev-only — a full run
needs every file). Re-runs skip already-ingested consumption files
(`intermediate/ingest_manifest.json`) unless `--no-resume` is passed.

Remove `--limit-files 1` only after checking the first real run's log and output.
The cohort is selected before ingest: `CohortConfig(labeled_only=False,
extra_random_gps=300, seed=42)` keeps every GP with at least one known asset label
and an unambiguous MP link, plus a seeded sample of the other valid Table 4 GPs.
Explicit negative labels count as known; four null labels do not. If fewer extra
GPs are available than requested, all available extras are used. `--labeled-only`
omits extras. Sorting the candidate IDs before sampling makes selection
independent of input row order. `--limit-buildings` deliberately truncates this
cohort for development and can omit labeled buildings; do not use it for full runs.

The wide consumption frame is joined to cohort MPs **before unpivot and before
any consumption group_by**. A separate bounded audit reads only identifiers and
OBIS codes. It reports unknown/missing OBIS codes as counts of raw daily rows
across the selected source files, not 96 times per quarter-hour.

The ingest cache includes mapping, cohort, thresholds and an ingest schema
version. A changed configuration refuses resume: choose a new output directory
or pass `--no-resume`. Each file is checkpointed after a successful sink. Errors
stop the run; a final `_manifest.json` is written only on success. Feature
assembly reads only the parts belonging to the current selected source files.
If other Parquet parts are present in `by_file/`, the run refuses to proceed:
use a new output directory. This also protects downstream loaders that glob
all parts. Expanding a one-file run to the full discovered set is supported.
The manifest records the active part paths and row counts.

There is no real AEW data on a laptop (see `backend/CLAUDE.md`), so
`scripts/make_synth_fixture.py` generates a small input set in the exact real
schemas, with known devices injected, for local development and
`tests/test_feature_pipeline.py`:

```sh
python3 scripts/make_synth_fixture.py --out data/synth_input --buildings 100 --days 400
```

## Deliverables

`cohort.parquet` has one row per selected GP:

| Column | Type | Meaning |
| --- | --- | --- |
| `gp_nr` | Int64 | Building key shared with model and export streams |
| `is_labeled` | Boolean | At least one known GIGI label and an unambiguous MP link |
| `plz` | String, nullable | Modal observed consumption PLZ (lexical tie-break), falling back to GIGI PLZ |

It is written before ingest (PLZ may initially be unknown), then updated from
the successfully ingested parts. Unknown GPs from Table 4 can have no measured
history: keep them with null features, `n_valid_days=0`, and possibly null PLZ.

`intermediate/by_file/*.parquet` are **permanent deliverables**, not disposable
temporary files. Each corresponds to one source CSV; a source-path hash in the
filename prevents basename collisions. They contain:

| Column | Type | Meaning |
| --- | --- | --- |
| `gp_nr` | Int64 | Six-digit numeric cohort building identifier |
| `ts` | Datetime(us), timezone-naive | Europe/Zurich local interval start |
| `import_kw` | Float32, nullable | Sum of import power across the building's MPs |
| `export_kw` | Float32, nullable | Sum of export power across the building's MPs |
| `net_kw` | Float32, nullable | Import minus export |
| `power_kw` | Float32, nullable | Alias of `net_kw`; the export stream's chart line |
| `plz` | String, nullable | Observed postal code for this building/interval |
| `num_mp_with_data` | UInt32 | Distinct MPs with usable net values at this interval |

The input values are kWh per quarter-hour: `unit_factor=4.0` converts them to
kW immediately after unpivot. The configured channels are import
`1-1:1.29.0*255` and export `1-1:2.29.0*255`; other channels are ignored and audited.
A completely absent export row defaults to zero. **An empty cell in an existing
export row remains null**, as do missing import values. `00:15` labels the
interval starting 00:00; the terminal `00:00` starts at 23:45 on the same Datum.
Blank days remain in the series; no interpolation or zero-filling is applied.

`feature_dataset.parquet` contains all columns in `pipeline.FINAL_COLUMNS`,
with exactly one row per cohort GP over the whole processed history:
`gp_nr` (Int64, six-digit), `plz` (String), `num_mp_ids` (Int32), `n_valid_days`
(Int32), all feature columns (Float64) and `label_pv`, `label_ev`, `label_heatpump`, `label_battery`
(nullable Int8, values 1/0/null). A valid day has at least 90 non-null net-power
intervals (`thresholds.min_valid_intervals_per_day`). A real zero is valid data.
`num_mp_ids` counts linked MPs, not only those present in a particular file.
`total_export_kwh` sums the export channel, not the negative part of building net
power, so simultaneous import on another MP does not hide the export energy.

`gigi_dates.parquet` is separate from the feature table. It contains
`gp_nr` and nullable Date columns `commissioned_pv`, `commissioned_ev`,
`commissioned_heatpump`, `commissioned_battery` for every cohort GP; GPs absent
from GIGI have all four dates null. The CLI writes this file by calling
`export_labels.load_gigi_dates(labels_file)`, matching the default `osnova train`
input path. The previous `commissioning_dates.parquet` name is no longer produced.
`export_labels.load_gigi_dates(labels_file)` can also be called independently.
For each asset-positive `x`/`X` row, choose the first parseable date in
`InBetrieb-Datum`, then `Übergabe`, then `Datum Unterschrift` order. Take the
earliest chosen date across that GP's positive rows for the asset. Negative and
unknown flags contribute no date; `geplanter Baustart` is never used. These
dates are for model-stream label cleaning only, never predictor columns.

The CLI also copies the input `HackDays2026 - GIGI.csv` next to the feature
dataset using ordinary streamed writes (no FUSE `copyfile` operation). This
preserves its original bytes and lets the exporter resolve Ort and Kanton.
For downstream commands set `OSNOVA_REGISTRY_DIR` to the original registry
folder or the feature output directory containing this copy. Do not commit
this copied client registry or real feature outputs to Git.

Other outputs: `ev_candidate_sessions.parquet`, `audit_report.json`, and
`_manifest.json` (git SHA, configuration/hash, inputs, row count, runtime and
active per-file Parquet paths). The audit and manifest include `rows_per_part`
and `feature_table_shape`, also printed to the console. The CLI republishes
the manifest after the GIGI dates and registry copy succeed; do not start
downstream stages until the CLI has returned successfully.
A limited-file manifest is explicitly marked
as such and is not evidence of complete historical coverage.

To inspect a July PV noon row on Renku, run the one-file check with
`--raw-consumption-glob '**/Juli 2025/LG_AIM2Hackerdays_kWh_*.csv' --limit-files 1`
in a fresh output directory. The default lexical first file is April 2023,
so it cannot provide a July example. Use the same cohort configuration for the
full run, restore the default glob and remove `--limit-files` after review.

## Weather and limitations

The supported ERA5 layout is `weather_part_*/hourly/<PLZ>/<YYYY-MM>.csv.gz`.
Unrelated CSVs are excluded by header before materialisation. UTC timestamps
are converted to local-naive Europe/Zurich; preceding-hour radiation, sunshine,
precipitation and snowfall are shifted back by one actual hour before the join.
Missing hours are not replaced by adjacent-row values. Legacy local `time`
exports are treated as interval-start labels. Duplicate local hours at fall-back
retain the first actual UTC occurrence to match the current local-naive contract;
this cannot represent both repeated real hours. Rows remain unique on `(plz, ts)`.

The full 43-file run is **not tested on real data locally**. Ambiguous MP-to-GP
links are dropped and audited rather than counted twice. A GP can have multiple
PLZ observations; the summary PLZ is a representative value, not a full address.
Partial multi-MP observations remain null at building level. Model streams must
apply their coverage policy and exclude null asset labels per target. Normalising
GP identifiers does not recover the measured registry join loss.

## Validation

From `backend/`, on synthetic data only:

```sh
uv run ruff check . && uv run ruff format --check . && uv run pytest
```
