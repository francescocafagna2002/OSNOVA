# backend/ — rules for Claude Code sessions

You are working on the OSNOVA prediction engine: Python pipeline that turns AEW 15-minute
smart-meter data into per-building PV / battery / heat pump / EV probabilities, events and
explanations for the Next.js frontend.

Read before coding:
- `docs/superpowers/specs/2026-09-10-prediction-engine-design.md` — architecture and schemas.
- `docs/superpowers/specs/2026-09-10-prediction-engine-team-plan.md` — streams, task cards, agent rules.
- `docs/superpowers/specs/data-check-*.md` — facts measured on the real data (when present).

## Hard rules

1. **No real data on this machine.** Never search for, read, or invent real AEW files. Everything
   local runs on synthetic data from `uv run osnova synth --out data/synth`. If you need a fact about
   the real files, stop and ask the human to run `osnova check-data` on Renku.
2. **Contracts are law.** Schemas live in `src/osnova/io/store.py` (Parquet) and
   `src/osnova/export/schema.py` (FE JSON, mirrors `frontend/src/lib/types.ts`). Change them only in a
   PR titled `contract: …` after telling the human. Everything else adapts to them.
3. **Config, not constants.** Every threshold, daypart, season, unit factor goes in `src/osnova/config.py`.
4. **Stay in your stream's directories** (`io/`, `features/`, `events/`+`export/`+`api/`, `labels/`+`models/`).
   Touching another stream's files or a shared file is a message to the human first.
5. **TDD on synth.** A feature or detector without a test that injects the asset and asserts recovery is not done.
6. **Report faithfully.** State what ran, what was skipped, and that real data was not tested.

## Commands

```bash
uv sync                                   # install (Python >= 3.11)
uv run osnova synth --out data/synth      # synthetic Tables 1–5 + truth.json
uv run osnova <stage> --help              # check-data | registry | ingest | weather | features | events | train | export | api
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

Definition of done for any task: ruff + pytest green, and the touched stage runs end-to-end on synth.

## Conventions

- polars lazy for anything reading `lastgang/`; `sink_parquet`, never `collect()` the whole cohort.
- numpy inside per-meter detectors; parallelise over lastgang buckets, not inside them.
- Feature functions: `def f(my: MeterYear, cfg: FeatureConfig) -> dict[str, float]`, registered with
  `@feature_group("<pv|battery|ev|heatpump|common>")`. Names are snake_case with unit suffixes (`_kw`, `_kwh`, `_ratio`, `_h`).
- Timestamps: local naive `Europe/Zurich`, interval start; the exporter attaches the real UTC offset.
- Every stage writes `_manifest.json` (git SHA, config hash, inputs, row counts, duration) next to its output.
- Commits: `feat(backend): …`, `fix(backend): …`, `docs: …`.
