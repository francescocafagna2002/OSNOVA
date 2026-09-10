# backend/ — rules for Claude Code sessions

You are working on the OSNOVA prediction engine: Python pipeline that turns AEW 15-minute
smart-meter data into per-building PV / battery / heat pump / EV probabilities, events and
explanations for the Next.js frontend.

Read before coding:
- `docs/superpowers/specs/2026-09-10-prediction-engine-design.md` — architecture and schemas; start with
  its "Revision 2026-09-11" section.
- `docs/superpowers/specs/2026-09-10-prediction-engine-team-plan.md` — sessions, task cards, agent rules.
- `docs/superpowers/specs/data-check-*.md` — facts measured on the real data (when present).
- `feature_pipeline/README.md` — the ingest + feature engine.

## Grain (team decision 2026-09-11)

One row per **building**: `gp_nr` (Table 2 `GP-Nr` = Table 4 `GPartner`, 6 digits), whole history
2023-01 → 2026-07, all meters of the building summed. No `meter_id`, no `year` anywhere downstream of
`feature_pipeline`. The frontend id is `f"AG-{gp_nr}"`. Labels are three-valued per asset
(`x` = 1, `-` = 0, blank = unknown → excluded for that asset); `history` in `buildings.json` is `[]`.

## Two packages

| package | role | run |
| --- | --- | --- |
| `feature_pipeline/` (top-level under `backend/`) | ingest + weather + labels + features → `feature_dataset.parquet`, one row per `gp_nr` | `python3 scripts/build_feature_dataset.py …` from `backend/` |
| `src/osnova/` | labels, models, events, export, api (+ `check-data`, `weather`, `synth`) | `uv run osnova <stage>` |

`osnova registry|ingest|features` are retired stubs that point to `scripts/build_feature_dataset.py`.
Feature column names are `FINAL_COLUMNS` in `feature_pipeline/pipeline.py`; the key columns are
`FEATURE_KEYS` in `src/osnova/io/store.py` (`gp_nr`, `plz`, `n_valid_days`).

## Store layout (`$OSNOVA_STORE_DIR/osnova/`)

```
feature_output/feature_dataset.parquet       # feature_pipeline: keys + features + label_* per gp_nr
feature_output/ev_candidate_sessions.parquet # feature_pipeline debug output
feature_output/audit_report.json
feature_output/intermediate/by_file/*.parquet   # building series (gp_nr, ts, import/export/net kW)
feature_output/intermediate/ingest_manifest.json
weather/plz=XXXX.parquet                     # osnova weather (hourly, local naive)
predictions.parquet, models/                 # osnova train   (one row per gp_nr)
events.parquet, showcase.parquet             # osnova events  (keyed by gp_nr)
export/buildings.json, export/featured.json  # osnova export  (id = AG-{gp_nr})
data_check.json, _manifest_<stage>.json
```

`feature_pipeline/` (top-level under `backend/`, not under `src/osnova/`) is a
separate, already-implemented building-level (`GP-Nr`) feature extraction task
— see `feature_pipeline/README.md` for why it exists next to this design
instead of inside it, and what to port if/when Stream B's meter-year
`features/` gets built.

## Hard rules

1. **No real data on this machine.** Never search for, read, or invent real AEW files. Everything
   local runs on synthetic data from `uv run osnova synth --out data/synth`. If you need a fact about
   the real files, stop and ask the human to run `osnova check-data` on Renku.
2. **Contracts are law.** Schemas live in `src/osnova/io/store.py` (Parquet) and
   `src/osnova/export/schema.py` (FE JSON, mirrors `frontend/src/lib/types.ts`). Change them only in a
   PR titled `contract: …` after telling the human. Everything else adapts to them.
3. **Config, not constants.** Every threshold, daypart, season, unit factor goes in `src/osnova/config.py`.
4. **Stay in your session's directories** (`feature_pipeline/`; `labels/`+`models/`; `events/`+`export/`+`api/`; `io/`+`cli.py`+docs).
   Touching another stream's files or a shared file is a message to the human first.
5. **TDD on synth.** A feature or detector without a test that injects the asset and asserts recovery is not done.
6. **Report faithfully.** State what ran, what was skipped, and that real data was not tested.

## Commands

```bash
uv sync                                   # install (Python >= 3.11)
uv run osnova synth --out data/synth      # synthetic Tables 1–5 + truth.json
uv run osnova <stage> --help              # check-data | weather | events | train | export | api  (registry/ingest/features: retired)
python3 scripts/build_feature_dataset.py --help   # feature_pipeline: ingest + features (Renku; synth via scripts/make_synth_fixture.py)
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Definition of done for any task: ruff + pytest green, and the touched stage runs end-to-end on synth.

## Conventions

- polars lazy for anything reading the building series (`feature_output/intermediate/by_file/`); `sink_parquet`, never `collect()` the whole cohort.
- numpy inside per-building detectors; parallelise over buildings, not inside them.
- Features are polars expressions in `feature_pipeline/features.py` (vectorised, `.over("gp_nr")`); `features/base.py` in
  `src/osnova` is a calendar/weather helper only. Names are snake_case with unit suffixes (`_kw`, `_kwh`, `_ratio`, `_h`).
- Timestamps: local naive `Europe/Zurich`, interval start; the exporter attaches the real UTC offset.
- Every stage writes `_manifest.json` (git SHA, config hash, inputs, row counts, duration) next to its output.
- Commits: `feat(backend): …`, `fix(backend): …`, `docs: …`.
