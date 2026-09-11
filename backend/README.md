# OSNOVA Backend

Python prediction engine for the **Energy Fingerprints** challenge — the `osnova` pipeline turns
AEW 15-minute smart-meter data into per-building PV / battery / heat pump / EV probabilities,
one showcase day, event bands and SHAP explanations, exported as `buildings.json` for the frontend.

Read first:

- [Architecture and schemas](../docs/superpowers/specs/2026-09-10-prediction-engine-design.md)
- [Team plan: streams, task cards, agent rules](../docs/superpowers/specs/2026-09-10-prediction-engine-team-plan.md)
- [Implementation plan (task cards)](../docs/superpowers/plans/2026-09-10-prediction-engine.md)
- [`CLAUDE.md`](CLAUDE.md) — rules for Claude Code sessions in this directory

## Requirements

Python 3.11+ and [uv](https://docs.astral.sh/uv/). Dependencies are declared in
[`pyproject.toml`](pyproject.toml) and locked in `uv.lock`.

## Layout

```text
backend/
  pyproject.toml, uv.lock   # uv-managed project; console script `osnova`
  CLAUDE.md                 # agent rules
  src/osnova/
    config.py               # OsnovaSettings (paths from env) + every tunable threshold
    cli.py                  # `osnova <stage>`: one subcommand per pipeline stage
    io/                     # store.py (Parquet schemas, paths, manifests), weather.py, registry, ingest
    features/               # base.py (MeterYear, feature registry) + one module per asset group
    events/                 # rule-based detectors and the showcase-day picker
    labels/                 # meter-year labels from the registry
    models/                 # LightGBM training, prediction, SHAP, reasons text
    export/                 # schema.py (FE JSON contract) + buildings.json builder
    api/                    # optional read-only FastAPI app
    synth/                  # synthetic Tables 1-5 in the real file formats, with known injected assets
  feature_pipeline/         # building-level ingest + whole-history feature extraction
  tests/                    # pytest; every test runs on synthetic data in tmp_path
  scripts/preview_data.py   # print header + first ten records of each CSV in a mount
```

### Environment variables

| variable | meaning | default |
| --- | --- | --- |
| `OSNOVA_DATA_DIR` | Table 1 load-profile CSVs, any depth (Renku: `store/cleaned_data`) | `data/synth/aew-data` |
| `OSNOVA_REGISTRY_DIR` | Tables 2-4, any depth, found by header (Renku: `aew-data/test-blob/input_data`) | same as `OSNOVA_DATA_DIR` |
| `OSNOVA_WEATHER_DIR` | folder holding `weather_part_1/`, `weather_part_2/` (ERA5 download, see below) | `data/synth/weather` |
| `OSNOVA_STORE_DIR` | writable output store; everything lands under `$OSNOVA_STORE_DIR/osnova/` | `data/synth/store` |

Every stage also accepts `--config PATH`, a JSON file overriding the defaults in `config.py`
(for example `{"ingest": {"unit_factor": 1.0}}`).

### Weather input layout

The weather download (Open-Meteo, ERA5 model) is hourly **UTC** and looks like this; `osnova synth`
writes the same layout so every test sees it:

```text
$OSNOVA_WEATHER_DIR/
  weather_part_1/
    metadata.json, plz_coordinates.csv, swisstopo_postcodes_4326.csv.zip   # ignored
    hourly/<PLZ>/<YYYY-MM>.csv.gz                                          # PLZ,timestamp_utc,<variables>
    hourly/<PLZ>/<YYYY-MM>.json                                            # ignored
    _SUCCESS.json                                                          # only once the download is complete
  weather_part_2/ ...
```

Weather files are recognised by their header (`temperature_2m`) at any depth, so a flat
`open-meteo_<plz>.csv` with a local `time` column also works. The `weather` stage converts UTC to local
naive `Europe/Zurich` and relabels the previous-hour variables (radiation, sunshine, precipitation,
snowfall) from interval end to interval start; instantaneous variables are left as they are. Settings
live in `WeatherConfig`.

### Stages

Run in this order; each stage is idempotent and writes a `_manifest_<stage>.json` next to its output:

```text
check-data → registry → ingest → weather → features → events → train → export
```

`osnova synth` generates laptop development data; `osnova api` serves the exported JSON (optional).
Stages that are not implemented yet exit with code 2 and name the owning stream and card.

## Laptop loop (synthetic data only)

Real data never leaves Renku. Locally everything runs on synthetic files that use the real formats:

```sh
uv sync
uv run osnova synth --out data/synth        # Tables 1-5 + truth.json (gitignored)
uv run osnova <stage> --help
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

## Renku loop (real data)

```sh
git clone <repo> && cd OSNOVA/backend
uv sync
export OSNOVA_DATA_DIR=/path/to/cleaned_data          # Table 1 monthly CSVs
export OSNOVA_REGISTRY_DIR=/path/to/input_data        # Tables 2-4 (other mount)
export OSNOVA_WEATHER_DIR=/path/to/store        # the folder that contains weather_part_1/ and weather_part_2/
export OSNOVA_STORE_DIR=/path/to/output
mkdir -p "$OSNOVA_STORE_DIR/osnova/logs"
uv run osnova check-data --max-files 3 > check.md   # first; paste the report into the team chat
uv run osnova weather                               # a minute; prints rows per PLZ
nohup uv run osnova ingest > "$OSNOVA_STORE_DIR/osnova/logs/ingest.log" &
```

Measured facts about the real mounts: `docs/superpowers/specs/data-check-<date>.md`.

Then `weather`, `features`, `events`, `train`, `export`, and copy
`$OSNOVA_STORE_DIR/osnova/export/buildings.json` to `frontend/public/data/` (gitignored).

## Building-level feature dataset

`feature_pipeline/` turns raw consumption + MP-to-building mappings + hourly
weather + the GIGI label file into `feature_dataset.parquet` (one row per
`GP-Nr`). It does not train any model — see
[`feature_pipeline/README.md`](feature_pipeline/README.md) for its CLI and
output contracts. Local validation uses synthetic data only.

## Preview the data mount

Run from this directory — `scripts` is imported as a top-level package, so the
working directory has to be `backend/`:

```sh
python3 scripts/preview_data.py
```

It searches the current directory and its parents for an `aew-data` /
`aew_data` mount (including under `data/`), then recursively previews every
`.csv` and `.csv.gz`. Pass an explicit path if the mount lives elsewhere:

```sh
python3 scripts/preview_data.py /actual/path/to/aew-data
```

Keep previews in the Renku console. Never commit real customer records or
credentials, and write processing output to the organizer-provided `store`
mount rather than the read-only input mount.

## Tests

All tests run on synthetic data generated once per session into `tmp_path`
(see `tests/conftest.py`: fixtures `synth_dir`, `truth`, `settings`, `cfg`):

```sh
uv run pytest
```

Definition of done for any task: `uv run ruff check . && uv run ruff format --check . && uv run pytest`
green, and the touched stage runs end-to-end on synth.
