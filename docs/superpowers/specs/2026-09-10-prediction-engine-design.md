# Prediction Engine — Backend Architecture (Energy Fingerprints)

> Status: draft for team review, 2026-09-10.
> Companion: [`2026-09-10-prediction-engine-team-plan.md`](2026-09-10-prediction-engine-team-plan.md) (work split, parallel plan, AI-agent workflow).
> Frontend contract this must satisfy: `frontend/src/lib/types.ts` on `main`.

## 1. Goal

Turn the AEW smart-meter mounts on Renku into, per building:

1. four probabilities — PV, battery, heat pump, EV;
2. a one-day 15-minute net-power profile (the "showcase day");
3. typed activity windows (events) for that day, drawn as bands by the frontend;
4. an explanation: plain-language reasons plus signed SHAP contributions per asset.

Delivery is **batch**: the pipeline runs on Renku, writes Parquet intermediates and one `buildings.json` to the organiser `store` mount, and the JSON is copied to the laptop that runs the frontend (`frontend/public/data/`, gitignored). A small FastAPI app serves the same files for anyone who wants an HTTP API; it is optional for the demo.

Decisions already taken with the team:

| Decision | Choice |
| --- | --- |
| Approach | Feature table + one LightGBM per asset + rule-based event detector |
| Entity shown in the FE | one **meter** (`MP ID`), id `AG-<MP ID>`; label inherited from its `GPartner` |
| Event types | five: `ev_charging`, `pv_generation`, `heat_pump_heating`, `battery_cycle`, `high_consumption` (FE adds two) |
| Compute | Renku session (internet, `pip`/`uv`, `git clone` all work). Laptops: synthetic data only |
| Export scope | 10 featured buildings + ~200 random others, all with real predictions |
| Data path to FE | copy `buildings.json` to `frontend/public/data/`, gitignored |

## 2. Data

### 2.1 Sources (as seen on Renku)

| Table | Content | Key columns | Format |
| --- | --- | --- | --- |
| 1 Energy consumption | 15-min load profile, one row per meter × OBIS × day | `MP ID; OBIS-Code; Datum; PLZ; 00:15 … 23:45; 00:00` | ~43 semicolon CSVs in `year/month` folders |
| 2 Building / devices | asset registry, ~1k customers | `GP-Nr, PLZ, Ort, Kanton, WärmePumpe, PV, PV-Leistung in kWp, Batterie/Speicher, Ladestation für EV, Wärmepumpenboiler, Datum Unterschrift, geplanter Baustart, Übergabe, InBetrieb-Datum` | Excel |
| 3 Meter point map | `MP ID → Zählpunktbezeichnung` | | CSV/Excel |
| 4 Installation map | `Zählpunktbezeichnung → GPartner, Anlage` | | CSV/Excel |
| 5 Weather | Open-Meteo hourly per PLZ | `plz, latitude, longitude, elevation, utc_offset_seconds, timezone, …` + hourly `temperature_2m, relative_humidity_2m, cloud_cover, shortwave_radiation, direct_radiation, diffuse_radiation, sunshine_duration, precipitation, snowfall, wind_speed_10m` | CSV (team-fetched) |

Join chain: `T1.MP ID → T3 → Zählpunktbezeichnung → T4 → GPartner = T2.GP-Nr`.

### 2.2 Facts that shape the design

- **OBIS channels are separate rows.** `1-1:1.29.0*255` = active energy **import** load profile, `1-1:2.29.0*255` = **export**. Values are never negative. Net power for the FE = import − export. A meter with a non-zero export row is a near-certain PV owner; the export channel is a legitimate, strong feature and must be kept as such (`export_present`, `export_kwh_year`).
- **Units are unknown** (kWh per 15 min vs kW average). The `check-data` stage decides: if the sum of the 96 values of a typical import day is ≈ 5–40 the file is kWh/15 min and `power_kw = value × 4`; if it is ≈ 20–160 it is kW. The factor lives in config, never in feature code.
- **Column semantics**: columns are interval **ends** (`00:15` = 00:00–00:15; the last column `00:00` = 23:45–24:00 of the same `Datum`). Timestamps are stored as interval start, local time (`Europe/Zurich`), naive.
- **DST days** have 92 or 100 real intervals but 96 columns. The ingest step tolerates empty/duplicate cells on those two days per year and marks them `quality = "dst"`; features ignore them.
- **Labels are positive-unlabeled.** Table 2 lists ~1k customers with at least one asset; the other ~89k are unknown, not negative.
- **Commissioning dates** (`InBetrieb-Datum`, fallback `Übergabe`, fallback `Datum Unterschrift`) make labels time-dependent: an EV charger commissioned in 2025 is a negative in 2023. Labels are therefore defined **per meter-year**.
- **Several meters per GPartner** are possible (`Anlage`). Swiss heat pumps often have a separate meter on a heat-pump tariff. The registry step records `meters_per_gp` and the pipeline treats each meter as its own entity; curated demo buildings are single-meter. This is a documented limitation, not something we solve in the hackathon.

### 2.3 Cohort

Processing all 90k meters is not needed. The **cohort** is:

- every meter that joins to Table 2 (all labeled customers), plus
- a seeded random sample of `cohort.unlabeled_sample = 3000` unlabeled meters.

The ingest stage scans all 43 CSVs once, lazily, keeps only cohort rows, and writes Parquet. Everything downstream reads Parquet only. Growing the cohort later is a config change and a re-run of `ingest`.

## 3. Pipeline

Seven stages, each a CLI subcommand, each reading and writing Parquet/JSON under `OSNOVA_STORE_DIR/osnova/`. Every stage is idempotent and can be re-run alone.

```
check-data ─┐
            ├─ ingest ──► lastgang/    ─┐
registry ───┘                           ├─ features ──► features.parquet ─┐
weather ──────────────► weather/       ─┘                                 ├─ train ──► models/, predictions.parquet
                                                                          │
                          lastgang/ ───────────────────► events ──► events.parquet, showcase.parquet
                                                                          │
                 registry.parquet + predictions + events + lastgang ─────► export ──► buildings.json
```

### 3.1 `check-data` (Renku only, run first)

Prints the answers the rest of the pipeline depends on, and writes them to `store/osnova/data_check.json`:

- OBIS codes present with row counts; files and date range per year;
- unit heuristic result (kWh/15 min vs kW) with the sampled daily sums;
- null/duplicate pattern on DST days;
- meters per GPartner histogram; number of meters that join to Table 2; asset counts per year after applying commissioning dates;
- weather file schema, PLZ coverage vs the PLZs in Table 1, hour gaps.

Its output is pasted into the team chat and into `docs/superpowers/specs/data-check-<date>.md` so laptop-only developers and AI agents work from facts.

### 3.2 `registry`

Reads Tables 2, 3, 4 (Excel via `fastexcel`/`polars.read_excel`, CSV via polars), normalises column names, and writes:

`registry.parquet` — one row per meter:

| column | type | note |
| --- | --- | --- |
| `meter_id` | i64 | `MP ID` |
| `zaehlpunkt` | str | |
| `gp_nr` | i64 nullable | null → unlabeled |
| `anlage` | str nullable | |
| `plz` | str | from Table 1 (majority PLZ of the meter) |
| `ort`, `kanton` | str nullable | from Table 2 when labeled, else PLZ lookup |
| `meters_per_gp` | i32 | |
| `has_pv`, `has_battery`, `has_hp`, `has_ev`, `has_hp_boiler` | bool nullable | null when unlabeled |
| `pv_kwp` | f32 nullable | |
| `commissioned_on` | date nullable | first non-null of `InBetrieb-Datum`, `Übergabe`, `Datum Unterschrift` |

### 3.3 `ingest`

`pl.scan_csv` over every Table 1 file (`separator=";"`, `decimal_comma=False`, schema overrides for the 96 value columns as `f32`), filter `MP ID in cohort`, keep OBIS `1.29.0` and `2.29.0`, unpivot the 96 columns to long, pivot the two OBIS rows into `import_kw` / `export_kw`, apply the unit factor, and sink Parquet partitioned by **meter bucket** (`bucket = meter_id % 64`) so later stages parallelise over buckets and never load the full cohort at once.

`lastgang/bucket=NN/part.parquet`:

| column | type | note |
| --- | --- | --- |
| `meter_id` | i64 | |
| `ts` | datetime[ms] | interval start, local naive |
| `plz` | str | |
| `import_kw` | f32 | ≥ 0 |
| `export_kw` | f32 | ≥ 0, 0 when no export row exists |
| `net_kw` | f32 | import − export |
| `quality` | enum `ok\|dst\|missing` | |

Rough size for a 4k-meter cohort: 4k × 4 y × 35k intervals ≈ 560M rows, ~4–6 GB Parquet. Fine on Renku disk; never on a laptop.

### 3.4 `weather`

Normalises the team's Open-Meteo CSVs to `weather/plz=XXXX.parquet` with `ts` (hourly, local naive, same convention as lastgang) and the ten variables as `f32`. Adds derived hourly columns used by several features: `is_sunny_day` (daily shortwave sum ≥ 75th percentile of that PLZ-year), `is_cloudy_day` (≤ 25th), `hdd15` (max(0, 15 − temperature)).

At feature time the hourly frame of a PLZ is upsampled to 15 minutes first (temperature linearly interpolated, every other variable forward-filled) and then joined to the lastgang rows on `(plz, ts)`.

### 3.5 `features`

For every `(meter, year)` with ≥ `features.min_days = 300` days of `ok` data, build a `MeterYear` frame (lastgang rows of that year joined with weather, plus calendar columns `hour`, `minute_of_day`, `month`, `season`, `daypart`, `is_weekend`) and run every registered feature function. Output `features.parquet`, one row per meter-year, ~120 columns.

Feature functions are pure: `def f(my: MeterYear, cfg: FeatureConfig) -> dict[str, float]`. They are registered per group with a decorator and unit-tested on synthetic data.

Config constants (all in `config.py`, tunable):

| name | default |
| --- | --- |
| dayparts | night 00–06, morning 06–10, midday 10–16, evening 17–22 (local) |
| PV midday | 11–14 |
| summer / winter | Jun–Aug / Dec–Feb |
| near-zero | \|net_kw\| < 0.05 kW |
| EV thresholds | 3, 5, 7, 11 kW |
| EV session | residual ≥ 2.5 kW for ≥ 3 intervals, gap merge ≤ 2 intervals, plateau CV ≤ 0.25 |
| temperature bins | < −5, −5–0, 0–5, 5–10, 10–15, ≥ 15 °C |

#### Feature groups

**common** — `n_days`, `mean_kw`, `median_kw`, `p95_kw`, `night_baseline_kw` (p10 of 01–05), `daily_kwh_mean`, `weekend_weekday_ratio`, `export_present`, `export_kwh_year`, `share_missing`.

**pv** (team list + additions)
`daytime_mean_power, morning_mean_power, evening_mean_power, negative_consumption_ratio` (net < 0), `negative_daytime_consumption_ratio, total_export_kwh, days_with_export_ratio, summer_midday_mean, winter_midday_mean, summer_vs_winter_midday_diff, corr_radiation_net, corr_sunshine_net, sunny_day_midday_mean, cloudy_day_midday_mean`, plus `midday_dip_depth` (night baseline − sunny midday net), `export_peak_kw_p95` (≈ inverter size), `export_start_hour_median`.

**battery**
`pv_prob` (out-of-fold PV probability, second stage), `near_zero_interval_ratio, number_of_near_zero_blocks, daytime_near_zero_ratio, evening_near_zero_ratio, consumption_per_unit_solar_radiation`, plus `export_clipping_ratio` (share of sunny-midday intervals where export sits on a flat plateau while radiation still rises — battery charging), `evening_import_sunny_vs_cloudy` (evening import after sunny days ÷ after cloudy days; batteries push this well below 1), `export_delay_minutes` (sunrise-to-first-export lag on sunny days; batteries charge first).

**ev**
`count_events_above_{3,5,7,11}kw, median_consumption, p95_consumption, p99_consumption, max_consumption, max_positive_ramp, max_negative_ramp, p95_positive_ramp, p99_positive_ramp, p95_negative_ramp, p99_negative_ramp`; from the session detector (§3.6): `session_count, sessions_per_week, session_mean, session_median, session_std, session_variance, session_cv` (of session energy kWh), `session_plateau_kw_median, session_duration_median_h`, start-time shares `morning|midday|evening|night_start_ratio`, finish-time shares `…_finish_ratio`, `high_load_ratio` per daypart (share of intervals ≥ 3 kW). The `percentage_of_*` names in the team list are the same quantities as the `*_ratio` ones; we keep one name.

**heatpump**
`corr_temperature_net, mean_consumption_T_{below_-5,-5_to_0,0_to_5,5_to_10,10_to_15,above_15}, winter_night_mean_consumption, summer_night_mean_consumption, winter_summer_night_ratio`, plus `hdd_slope_kw_per_degc` (OLS slope of daily mean kW on daily HDD15 — the classic heating signature), `winter_cycling_autocorr` (autocorrelation of winter-night net at 30–60 min lags), `winter_daily_kwh_p90`.

### 3.6 `events`

Rule-based detectors on the full multi-year series of a meter (numpy per meter, parallel over buckets). Each detector returns rows for `events.parquet`:

| column | type |
| --- | --- |
| `meter_id` | i64 |
| `type` | enum of the five FE types |
| `start`, `end` | datetime (local naive) |
| `confidence` | f32 0–1 |
| `peak_kw`, `energy_kwh` | f32 |

Detectors:

- **EV sessions** — baseline = centred rolling median of `import_kw` over 8 h (a session must be shorter than half the window, otherwise the median absorbs it); residual = import − baseline; a session is a run of residual ≥ threshold for ≥ 3 intervals with plateau CV ≤ 0.25; confidence from plateau flatness and plateau level proximity to 3.7/7/11 kW. Sessions also feed the EV features (same code, one truth).
- **PV generation** — on days with export: window from first to last interval with `export_kw > 0.1` or, without export channel, the contiguous midday interval where net < 0.5 × night baseline on a sunny day. Confidence from radiation correlation that day.
- **Heat-pump heating** — winter days: intervals where import exceeds the summer-night baseline by ≥ 0.8 kW with a cycling pattern (≥ 3 on/off transitions in 3 h) or a sustained morning block; confidence from the meter-year `hdd_slope`.
- **Battery cycle** — sunny days on meters with `export_present`: the morning block where net ≈ 0 while radiation rises (charging) and the evening block where net ≈ 0 while the typical evening peak is expected (discharging). Confidence from `evening_import_sunny_vs_cloudy`.
- **High consumption** — fallback band: the longest run ≥ 1 h above p95 of the day that no other detector claimed.

`showcase.parquet` — one row per meter: `showcase_date` and the events on that day (plus the evening before, because EV sessions cross midnight and the FE folds them). The showcase day maximises the number of **distinct** event types with confidence ≥ 0.6, tie-break on the sum of confidences, then the most recent date. PV and heat pump rarely coincide on one day; the exporter records which assets have evidence on the chosen day and which have evidence elsewhere so the reasons text can say so.

### 3.7 `train`

`labels/build.py` produces `labels.parquet`, one row per meter-year and asset:

- registry meter, asset flag true, `commissioned_on ≤ Jan 1 of year` → **positive**, weight 1;
- registry meter, asset flag true, commissioning inside the year → dropped for training (kept for the change-over-time story);
- registry meter, asset flag false → **negative**, weight 1 (a customer in the registry for PV but without a charger is a fairly reliable EV negative);
- unlabeled cohort meter → **negative**, weight `labels.unlabeled_weight = 0.5` (positive-unlabeled assumption; base rates in Aargau are low enough for this to be mostly right).

Four LightGBM binary classifiers (`models/train.py`), `GroupKFold(5)` grouped by `gp_nr` (unlabeled meters group by themselves) so a building never leaks across folds. Battery is trained second with the out-of-fold PV probability as a feature. Class imbalance via `scale_pos_weight`. Metrics on the registry-only holdout (clean labels) and on all rows: ROC-AUC, PR-AUC, precision/recall at the FE thresholds (50 %, 80 %), Brier. Probabilities are calibrated with isotonic regression on out-of-fold scores of registry rows. A rule-based baseline score per asset (weighted thresholds on the same features) is reported next to the model so the presentation can show the gain.

Artifacts: `models/<asset>.txt` (LightGBM), `models/<asset>_calibration.pkl`, `models/metrics.json`, `models/feature_importance.parquet`, `predictions.parquet` (one row per meter-year: `prob_pv, prob_battery, prob_hp, prob_ev`, `shap_<asset>` as JSON list of top-6 signed contributions in feature units, scaled to roughly −1..1 for the FE).

`models/reasons.py` turns features + events into the FE `reasons` bullets with templates, e.g. `"{sessions_per_week:.1f} charging-like sessions per week, plateau ≈ {plateau_kw:.1f} kW"`, `"Evening import after sunny days is {ratio:.0%} of cloudy days"`. Never phrased as fact; templates live in one file for copy-editing.

### 3.8 `export`

`export/build_json.py` joins registry, the **latest complete year** of `predictions.parquet`, `showcase.parquet` and that day's lastgang, validates with the Pydantic schema, and writes `buildings.json`. The schema mirrors `frontend/src/lib/types.ts` exactly, plus additive fields the FE may ignore:

```jsonc
{
  "id": "AG-053628",
  "postcode": "5105",
  "city": "Auenstein",
  "canton": "AG",
  "predictions": { "pv": 92, "battery": 48, "heatPump": 31, "ev": 76 },   // 0–100
  "electricity": [ { "timestamp": "2025-06-18T00:00:00+02:00", "powerKw": -1.23 }, … ],  // 96 points, net, negative = export
  "events": [ { "type": "ev_charging", "start": "…", "end": "…", "confidence": 0.9 } ],
  "explanation": {
    "model": "LightGBM gradient-boosted trees, one per asset",
    "inputs": ["15-minute import and export load profiles, 2022–2025"],
    "additionalData": ["Open-Meteo hourly weather per postcode"],
    "method": "SHAP",
    "methodDescription": "SHAP shows which features contributed most to the prediction.",
    "assets": { "pv": { "reasons": ["…"], "shap": [ { "feature": "Midday net-load dip", "contribution": 0.38 } ] }, … }
  },
  // additive, not in the FE type yet:
  "featured": true,
  "profileDate": "2025-06-18",
  "groundTruth": { "pv": true, "battery": false, "heatPump": null, "ev": true },   // null = unlabeled
  "history": [ { "year": 2023, "predictions": { … } }, { "year": 2024, "predictions": { … } } ]
}
```

`export/curate.py` picks the featured 10: labeled, single-meter, at least two assets with probability ≥ 80 % that agree with the ground truth, at least three distinct event types on the showcase day, spread over ≥ 5 PLZs. The other ~200 are a seeded random sample of the remaining cohort, stratified so each asset has some "Likely" cases. The list is written to `export/featured.json` so the same buildings come back on a re-run, and IDs can be pinned by hand.

Timestamps are emitted with the real UTC offset of the showcase day (`+01:00` or `+02:00`); the FE computes minutes from the first point, so any offset works as long as it is consistent within the day.

### 3.9 `api` (optional)

FastAPI, read-only, serving the exported files: `GET /buildings` (the JSON), `GET /buildings/{id}`, `GET /buildings/{id}/profile?date=YYYY-MM-DD` (any day from lastgang, with that day's events) and `GET /health`. Same Pydantic models as the exporter. Useful if the FE later gets a date picker; not on the demo's critical path.

## 4. Code layout

```
backend/
  pyproject.toml            # uv-managed; deps: polars, pyarrow, numpy, scikit-learn, lightgbm, shap,
                            # pydantic, pydantic-settings, typer, fastexcel, fastapi, uvicorn
                            # dev: pytest, hypothesis, ruff, mypy
  uv.lock
  CLAUDE.md                 # agent rules (see team plan)
  src/osnova/
    config.py               # OsnovaSettings (paths from env), FeatureConfig, EventConfig, LabelConfig
    cli.py                  # typer app: check-data, registry, ingest, weather, features, events, train, export, api, synth
    io/                     # lastgang.py, registry.py, weather.py, store.py (paths + read/write helpers)
    features/               # base.py (MeterYear, registry decorator), common.py, pv.py, battery.py, ev.py, heatpump.py, build.py
    events/                 # ev_sessions.py, pv_windows.py, hp_heating.py, battery_cycles.py, high_load.py, showcase.py, run.py
    labels/build.py
    models/                 # train.py, predict.py, explain.py, reasons.py, baseline.py
    export/                 # schema.py (Pydantic = FE types), build_json.py, curate.py
    api/app.py
    synth/                  # generator of realistic fake Table 1/2/3/4/5 files in the real formats
  tests/                    # pytest; every test runs on synth data in tmp_path
  scripts/preview_data.py   # kept
```

Conventions: polars lazy for anything that touches `lastgang/`; numpy inside per-meter detectors; all thresholds in `config.py`; feature names are the column names, snake_case, unit suffix where not obvious (`_kw`, `_kwh`, `_ratio`, `_h`).

## 5. Synthetic data (the local development contract)

Real data never leaves Renku, so `osnova synth --out data/synth --meters 60 --years 2` must produce files in the **exact real formats** (semicolon CSV with the 96 columns and OBIS rows, Excel registry, Open-Meteo-shaped weather) with injected, parameterised fingerprints:

- PV: export channel = clear-sky bell × cloud factor from the synthetic weather, sized by `pv_kwp`;
- EV: 2–4 evening/night sessions per week, plateau 3.7/7/11 kW, 1.5–4 h;
- heat pump: import rises linearly with HDD15 plus 30–45 min on/off cycling in winter;
- battery: clamps net to ≈ 0 while charging from PV surplus and discharging in the evening, capacity-limited.

The generator writes the ground truth it used, so tests assert that detectors and features recover it. The whole pipeline runs end-to-end on synth in under two minutes on a laptop; that is the CI job.

## 6. Error handling and data quality

- A meter-year with < 300 `ok` days is skipped for features (logged, counted in `features_skipped.parquet`).
- A meter without a weather PLZ match gets weather features as null; LightGBM handles nulls; the exporter marks `additionalData` accordingly.
- Unknown OBIS codes are counted and ignored; unparseable dates fail the ingest of that file loudly rather than silently dropping rows.
- Every stage writes a `_manifest.json` (git SHA, config hash, input paths, row counts, duration) next to its output so a re-run can be traced.

## 7. Testing

- Unit tests per feature group and per detector on synth `MeterYear` frames with known injected assets.
- Schema tests: `export/schema.py` round-trips the FE fixture `frontend/src/test/fixtures.ts` shape; a generated `buildings.json` from synth is validated by the FE's vitest suite (one test in `frontend` that loads `public/data/buildings.json` when present).
- Pipeline test: `osnova synth` → all stages → `buildings.json` in `tmp_path`, asserting counts and that featured buildings have ≥ 3 event types.
- Model test on synth: ROC-AUC ≥ 0.9 per asset (synth is easy; this catches wiring bugs, not model quality).
- Renku smoke: `check-data`, then `ingest --limit-files 1` before the full run.

## 8. Known limitations (say them in the presentation)

- Positive-unlabeled labels bias probabilities downward for rare assets; we report registry-only metrics.
- One meter per entity: households with a separate heat-pump meter are seen as two buildings.
- Rule-based detectors have hand-tuned thresholds; the model's SHAP values are the primary evidence, events are illustrative.
- The FE chart shows one showcase day; seasonal behaviour is in the `history` field and the reasons text.
