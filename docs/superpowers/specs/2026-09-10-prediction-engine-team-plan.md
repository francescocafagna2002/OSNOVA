# Prediction Engine — Team Plan: work split, parallel execution, AI agents

> Companion to [`2026-09-10-prediction-engine-design.md`](2026-09-10-prediction-engine-design.md). Read that first.
> Audience: the 2–3 people on backend/ML and every Claude Code session working on `backend/`.

## 1. Principle: contracts first, then four independent streams

The design has eight file contracts (Parquet/JSON schemas in §3 of the design). Once those exist as code — Pydantic/polars schemas plus a synthetic data generator that produces them — four people (or four agents) can work without waiting for each other, because every stream's input can be generated locally and every stream's output has a schema test.

```
T0  Skeleton + contracts + synth        (one person + one agent, ~2–3 h, blocks everything)
      │
      ├── Stream A  Data on Renku      registry, ingest, weather, check-data
      ├── Stream B  Features           common, pv, battery, ev, heatpump
      ├── Stream C  Events + Export    detectors, showcase, JSON export, curate, FE glue, API
      └── Stream D  Models             labels (PU), train, calibrate, SHAP, reasons, baseline
      │
T2  Integration run on Renku, curate featured 10, copy JSON to FE, presentation
```

Nobody touches another stream's directory without a message. Shared files (`config.py`, `io/store.py`, `features/base.py`, `export/schema.py`) are owned by T0 and changed only via small PRs that the owner reviews within the hour.

## 2. T0 — skeleton (do this first, together)

Owner: Steven + one Claude Code session. Output is a PR to `main` that everyone rebases on.

1. `backend/pyproject.toml` rewritten for `uv` (`[project]` + `[tool.uv]`, `src/` layout, `osnova` console script), `uv.lock` committed. Python `>=3.11`. Add `backend/data/` and `frontend/public/data/` to the root `.gitignore` (the existing `data/*` rule only covers the repo root).
2. `src/osnova/config.py`: `OsnovaSettings` (pydantic-settings; env `OSNOVA_DATA_DIR`, `OSNOVA_STORE_DIR`, `OSNOVA_WEATHER_DIR`), `FeatureConfig`, `EventConfig`, `LabelConfig`, `CohortConfig` with the defaults from the design.
3. `src/osnova/io/store.py`: path helpers and the polars schemas for `registry`, `lastgang`, `weather`, `features`, `labels`, `events`, `showcase`, `predictions` as `pl.Schema` constants + `assert_schema(df, name)`.
4. `src/osnova/features/base.py`: `MeterYear` (frozen dataclass: `meter_id`, `year`, `plz`, `df: pl.DataFrame` with the documented columns), `@feature_group("pv")` registry, `run_all(my, cfg) -> dict`.
5. `src/osnova/export/schema.py`: Pydantic models mirroring `frontend/src/lib/types.ts` plus the additive fields.
6. `src/osnova/synth/`: generator for Tables 1–5 in the real formats with injected assets and a `truth.json`. This is the single most valuable T0 deliverable — every other stream tests against it.
7. `src/osnova/cli.py` with all subcommands stubbed (`typer`), each raising `NotImplementedError` with the owning stream's name.
8. `tests/conftest.py` with a session-scoped `synth_dir` fixture; `tests/test_synth.py`; `ruff` + `pytest` in a GitHub Actions workflow (`.github/workflows/backend.yml`) running on `backend/**` changes.
9. `backend/CLAUDE.md` (already drafted, see §6) and `backend/README.md` updated with the stage list and the env vars.

Definition of done: `uv sync && uv run osnova synth --out /tmp/s && uv run pytest` green on a laptop; PR merged.

## 3. Streams

Each stream has an owner, a directory, an input it can generate, an output schema, and a set of task cards (§7). Streams are ordered by risk inside themselves: do the item that can fail on real data first.

### Stream A — Data on Renku (`io/`, `cli check-data|registry|ingest|weather`)

Owner: the person with the Renku session open. This is the only stream that sees real data, so its first job is to reduce uncertainty for everyone else.

1. `check-data` on the real mount (design §3.1). Paste the output into the chat **and** commit it as `docs/superpowers/specs/data-check-2026-09-1x.md`. Update `config.py` unit factor and OBIS codes from it.
2. `registry` — Excel/CSV loading, joins, `registry.parquet`. Report join loss (meters in Table 1 not in Table 3, etc.).
3. `ingest` with `--limit-files 1`, check row counts and a plotted day for a known PV customer (export bell) before the full run. Full run in the background (`nohup`, log to store).
4. `weather` normalisation, PLZ coverage report.
5. Hand over: the four Parquet directories exist under `store/osnova/`, `_manifest.json` present.

Risks: file encodings, `Datum` format, DST cells, memory on the full scan (use `sink_parquet`, never `collect()` on the cohort). If Renku RAM is tight, run ingest per year.

### Stream B — Features (`features/`, `cli features`)

Owner: the ML-minded person. Inputs: `MeterYear` frames from synth. Outputs: `features.parquet`.

Order: `common` → `ev` (needs the session detector from Stream C: until it lands, use the interface stub `events.ev_sessions.detect(import_kw, ts, cfg) -> pl.DataFrame` that Stream C publishes in T0+1h) → `pv` → `heatpump` → `battery` (last, needs `pv_prob`; use the true synth PV flag as a placeholder feature until Stream D delivers out-of-fold probabilities).

Each feature function has a test that injects the asset into synth and asserts the feature moves in the expected direction (e.g. `hdd_slope_kw_per_degc` > 0.1 with a heat pump, < 0.03 without). `features/build.py` parallelises over lastgang buckets with `concurrent.futures.ProcessPoolExecutor`.

### Stream C — Events, export, FE glue (`events/`, `export/`, `api/`, `cli events|export|api`)

Owner: the person closest to the frontend. Inputs: synth lastgang. Outputs: `events.parquet`, `showcase.parquet`, `buildings.json`.

Order: EV session detector first (Stream B depends on it) → PV windows → high-load fallback → showcase-day selection → `build_json.py` producing a valid `buildings.json` from synth with placeholder probabilities → **FE PR**: add `heat_pump_heating` and `battery_cycle` to `EVENT_TYPES`, `EVENT_META`, `BAND_OPACITY`, `BAND_LABEL_COLOR`; change `fetchBuildings()` to `fetch("/data/buildings.json")` with a fallback to mocks when the file is missing; add `frontend/public/data/` to `.gitignore` → heat-pump and battery detectors → `curate.py` → FastAPI.

The FE PR is small but should land early so the FE team can review the real JSON on synth data before real data exists.

### Stream D — Models (`labels/`, `models/`, `cli train`)

Owner: the second ML person (or the same as B, sequentially). Inputs: `features.parquet` + `registry.parquet` from synth (Stream B's partial output is enough to start; the label builder only needs the registry).

Order: `labels/build.py` with the commissioning-date rule and PU weights (tests on synth registry with dates) → `train.py` with `GroupKFold`, metrics JSON, baseline scores → calibration → `explain.py` (SHAP top-6, scaled) → `reasons.py` templates → second-stage battery with OOF `pv_prob` → `predict.py` for the latest year.

Keep the model boring: default LightGBM params, `num_leaves=31`, `n_estimators` by early stopping on the OOF fold. Tuning is the last thing to do, not the first.

## 4. Timeline (1.5–2 days)

| When | What | Who |
| --- | --- | --- |
| Day 1, 09:00–12:00 | T0 skeleton PR; Stream A runs `check-data` in parallel | Steven + agent; Renku owner |
| Day 1, 12:00 | Sync: data-check facts posted, config updated, streams start | all |
| Day 1 afternoon | A: registry + ingest limited run; B: common + ev features; C: EV detector + JSON export on synth + FE PR; D: labels + train on synth | 4 parallel |
| Day 1 evening | A: full ingest running; C: PV/HP/battery detectors; B: pv + heatpump; D: SHAP + reasons | |
| Day 2 morning | Integration on Renku: `features` → `train` → `events` → `export` on real data. Fix what breaks | everyone in one room |
| Day 2 midday | `curate` featured 10, eyeball each one in the FE, copy JSON, freeze | C + Steven |
| Day 2 afternoon | Metrics slide, limitations slide, demo rehearsal with the FE flow in `frontend/docs/energy-fingerprints-task.md` §19 | all |

Cut list if late, in order: FastAPI → battery second stage (use single stage) → calibration → heat-pump/battery detectors (reasons text only) → `history` field.

## 5. Git and environment workflow

- Branch per stream: `feat/be-data`, `feat/be-features`, `feat/be-events`, `feat/be-models`. Rebase on `main` at least twice a day; PRs are small and merged by the owner after CI is green, no waiting for a second reviewer during the hackathon unless a shared file changed.
- Commit messages: `feat(backend): …`, `fix(backend): …`, `docs: …`, matching the existing log.
- Laptop: `cd backend && uv sync && uv run osnova synth --out data/synth` (`data/*` is gitignored). All tests use synth. **No real data on laptops, ever.**
- Renku: `git clone`, `uv sync`, export `OSNOVA_DATA_DIR=/path/to/aew-data OSNOVA_STORE_DIR=/path/to/store OSNOVA_WEATHER_DIR=…`, run stages with `uv run osnova <stage>`. Long stages under `nohup … > $OSNOVA_STORE_DIR/osnova/logs/<stage>.log &`.
- The stray `1/1.py` on `main` should be deleted or moved in the T0 PR.

## 6. Working with AI agents (Claude Code)

The repo already uses the `superpowers` plugin (brainstorming → writing-plans → TDD → verification). This section says how to apply it to four parallel backend streams without agents stepping on each other or on the data rules.

### 6.1 Ground rules an agent must follow (encoded in `backend/CLAUDE.md`)

1. **Never look for, read, or fabricate real data.** Laptops have only synth data. If a task needs a fact about the real files, the agent stops and asks the human to run `osnova check-data` on Renku (or reads the committed `data-check-*.md`).
2. **Contracts are law.** Schemas in `io/store.py` and `export/schema.py` are changed only in a dedicated PR titled `contract:`; everything else adapts.
3. **Config, not constants.** Any threshold goes into `config.py`.
4. **TDD on synth.** A feature or detector without a test that injects the asset and asserts recovery is not done.
5. **Definition of done** for any task: `uv run ruff check . && uv run ruff format --check . && uv run pytest` green, plus `uv run osnova synth … && uv run osnova <stage> …` runs end-to-end for the touched stage.
6. **Stay in your stream's directories.** A change outside them is a message to the human first.
7. **Report faithfully.** Skipped tests, xfails, or "works on synth, untested on real data" are stated in the final message.

### 6.2 One agent per stream, in its own worktree

Each human runs one Claude Code session for their stream in a git worktree (`superpowers:using-git-worktrees`, or the app's worktree isolation). Four sessions, four worktrees, four branches. The session prompt is the task card (§7). Because the skeleton already contains stubs and schemas, an agent can implement a card end-to-end with tests and open a PR without needing the other streams.

Recommended session flow per card:

1. Paste the card. The agent reads `CLAUDE.md`, the design spec section named on the card, and the schema files.
2. Agent uses `superpowers:test-driven-development`: write the synth-based test first, then the implementation.
3. Agent runs the definition-of-done commands and reports output verbatim.
4. Human skims the diff, runs `uv run pytest` once locally, merges.
5. For Stream A only: the agent writes the code, the human runs it on Renku and pastes the log or error back into the session.

### 6.3 What agents are good at here, and what they are not

Good: feature functions with clear formulas, detectors with synthetic tests, schema/CLI plumbing, the JSON exporter, the FastAPI app, the FE glue PR, docstrings and the README, turning `metrics.json` into presentation tables.

Not good without a human: deciding thresholds from real data, judging whether a showcase day "looks sexy", anything that requires looking at real rows on Renku, and the final curation of the featured 10. Plan for the human to do those and feed results back.

### 6.4 Coordination between sessions

- `main` is the message bus: merge early, rebase often. An agent that needs another stream's function uses the T0 stub signature and writes a test that will pass once the real implementation lands.
- If two agents must change the same shared file, the human merges the first PR before the second agent starts that part.
- Keep a `docs/superpowers/plans/2026-09-10-prediction-engine.md` checklist (produced by `superpowers:writing-plans` after this plan is approved) with one line per card and its status; each PR ticks its line.

## 7. Task cards

Cards are self-contained prompts. Copy one into a fresh Claude Code session in the stream's worktree. Each names its spec section, files, interface, acceptance test, and what is out of scope. The full list is generated by the implementation plan; the shape is:

```
Task B3 — heat-pump features
Spec: design §3.5 "heatpump". Stream B. Files: src/osnova/features/heatpump.py, tests/test_features_heatpump.py.
Interface: register functions with @feature_group("heatpump"); each takes (my: MeterYear, cfg: FeatureConfig) and returns dict[str, float].
Implement: corr_temperature_net, mean_consumption_T_* (six bins), winter_night_mean_consumption,
  summer_night_mean_consumption, winter_summer_night_ratio, hdd_slope_kw_per_degc, winter_cycling_autocorr, winter_daily_kwh_p90.
Acceptance: on synth meters with has_hp=True, hdd_slope_kw_per_degc > 0.1 and corr_temperature_net < -0.3;
  on has_hp=False, hdd_slope < 0.03. Missing weather → all weather-based features are NaN, no exception.
Out of scope: the heating event detector (Stream C), any change to config.py defaults.
Done when: ruff + pytest green; `uv run osnova features --store data/synth_store` produces the new columns.
```

Card index (owner → cards):

- **T0**: T0-1 pyproject/uv, T0-2 config, T0-3 store schemas, T0-4 features/base, T0-5 export/schema, T0-6 synth generator, T0-7 CLI stubs + CI, T0-8 CLAUDE.md/README.
- **A**: A1 check-data, A2 registry, A3 ingest, A4 weather, A5 Renku full run + manifests.
- **B**: B1 common, B2 ev features (with detector stub), B3 heatpump, B4 pv, B5 battery, B6 build.py parallel runner.
- **C**: C1 ev_sessions detector, C2 pv_windows, C3 high_load + showcase, C4 build_json + curate, C5 FE glue PR, C6 hp_heating + battery_cycles, C7 FastAPI.
- **D**: D1 labels (PU, commissioning), D2 train + metrics + baseline, D3 calibration, D4 SHAP + reasons, D5 battery second stage + predict latest year.

## 8. Presentation checklist (so it is built, not improvised)

- Pipeline diagram (design §3) and the data facts from `check-data`.
- `metrics.json` → one table: per asset ROC-AUC / PR-AUC on registry-only holdout, model vs rule baseline.
- One SHAP summary plot per asset (from `explain.py`, saved to `store/osnova/models/plots/`).
- Two featured buildings walked through in the FE: one EV+PV, one heat pump.
- Change-over-time: one building whose `history` shows PV probability jumping in the commissioning year.
- Limitations slide = design §8.
