# Prediction Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Revision 2026-09-11 — building (`gp_nr`) grain on top of `feature_pipeline`.** Team decision: the grain is one row per building (`gp_nr`, whole history), FE id `f"AG-{gp_nr}"`. `backend/feature_pipeline/` (branch `feat/backend-feature-pipeline`) is the ingest + feature engine and handles the real layouts, so cards A2, A3 and B1–B6 are **superseded** (banner on each card). Per-year labels and the `history` field are dropped: labels are three-valued per asset from the GIGI flags (`x` = 1, `-` = 0, blank = unknown, excluded per asset), positives commissioned after 2025-07-01 are excluded, unlabeled buildings are weak negatives; `buildings.json` emits `history: []` and `groundTruth` from the labels. C and D cards carry a one-line grain banner; read them with `meter_id` → `gp_nr` and no `year`. The work is split into four sessions (design spec, "Revision 2026-09-11"; team plan §1). `FEATURE_KEYS` in `io/store.py` is `gp_nr, plz, n_valid_days` (commit `contract: feature keys are gp_nr`); `PREDICTIONS`/`LABELS` change in Session 2's contract commit, `EVENTS`/`SHOWCASE` in Session 3's. Cards T0-1…T0-8, A1 and A4 are done. Everything below is the 2026-09-10 plan, kept as written.

**Goal:** Build the batch pipeline that turns AEW 15-minute smart-meter data into `buildings.json` for the frontend: four asset probabilities, one showcase day, event bands and SHAP explanations per building.

**Architecture:** Seven CLI stages over Parquet on the Renku `store` mount (registry → ingest → weather → features → events → train → export). A synthetic-data generator that writes the real file formats makes every stage testable on laptops without real data. Four streams (data, features, events+export, models) run in parallel after a shared skeleton (T0) fixes the schemas.

**Tech Stack:** Python 3.11+, uv, polars (lazy), numpy, LightGBM, scikit-learn, shap, pydantic v2 + pydantic-settings, typer, fastexcel/xlsxwriter, FastAPI, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-10-prediction-engine-design.md` (architecture) and `docs/superpowers/specs/2026-09-10-prediction-engine-team-plan.md` (streams, agent rules).

## Global Constraints

- Python `>=3.11`; dependencies managed by `uv`; `uv.lock` committed.
- **No real data on laptops.** Every test runs on `osnova synth` output in `tmp_path`. Agents that need a real-data fact stop and ask for `osnova check-data` output.
- Schemas in `src/osnova/io/store.py` and `src/osnova/export/schema.py` are the contract; changed only in a PR titled `contract: …`.
- All thresholds in `src/osnova/config.py`. Defaults: dayparts night 00–06, morning 06–10, midday 10–16, evening 17–22; PV midday 11–14; summer Jun–Aug, winter Dec–Feb; near-zero |net| < 0.05 kW; EV thresholds 3/5/7/11 kW; EV session residual ≥ 2.5 kW for ≥ 3 intervals, gap merge ≤ 2, plateau CV ≤ 0.25; temperature bins < −5, −5–0, 0–5, 5–10, 10–15, ≥ 15 °C; `min_days = 300`; `unlabeled_weight = 0.5`; `unlabeled_sample = 3000`.
- Timestamps: local naive `Europe/Zurich`, interval **start**. CSV columns are interval ends (`00:15` = 00:00–00:15; last column `00:00` = 23:45–24:00 of the same `Datum`).
- OBIS: import `1-1:1.29.0*255`, export `1-1:2.29.0*255`. Values ≥ 0. `net_kw = import_kw − export_kw`. Unit factor default 4.0 (kWh/15 min → kW); `check-data` may set it to 1.0.
- Internal asset names: `pv`, `battery`, `heat_pump`, `ev`. FE keys: `pv`, `battery`, `heatPump`, `ev`. FE probabilities are integers 0–100.
- Event types: `ev_charging`, `pv_generation`, `heat_pump_heating`, `battery_cycle`, `high_consumption`.
- Definition of done for every task: `uv run ruff check . && uv run ruff format --check . && uv run pytest` green from `backend/`, plus the touched stage runs on synth. Commit messages `feat(backend): …` / `fix(backend): …` / `docs: …` / `contract: …`.
- Every stage writes `_manifest.json` next to its output via `Store.write_manifest`.

## Execution order

```
Phase 0  (serial, ~3 h)      T0-1 → T0-2 → T0-3 → T0-4 → T0-5 → T0-6 → T0-7 → T0-8        Steven + 1 agent
                             A1 check-data can start as soon as T0-1 is merged             Renku owner
Phase 1  (4 parallel)        A2, A3, A4          | B1              | C1 (first!) then C2, C3 | D1, D2
Phase 2  (4 parallel)        A3 full run on Renku| B2 (needs C1), B3, B4 | C4, C5           | D3, D4
Phase 3  (4 parallel)        A5 manifests/handover | B5, B6          | C6, C7               | D5
Phase 4  (together on Renku) features → train → events → export → curate → copy JSON → rehearse
```

Cut list if late, in order: C7 → D5 second stage (single-stage battery) → D3 → C6 → `history` field.

## File structure

```
backend/
  pyproject.toml, uv.lock, CLAUDE.md, README.md
  src/osnova/
    __init__.py
    config.py                 T0-2   settings + config models
    cli.py                    T0-7   typer app, one subcommand per stage
    io/
      __init__.py
      store.py                T0-3   paths, pl.Schema constants, assert_schema, manifests
      weather.py              T0-3 (upsample_15min) + A4 (normalize)
      registry.py             A2
      lastgang.py             A3
      check_data.py           A1
    features/
      __init__.py
      base.py                 T0-4   MeterYear, registry decorator, run_all, make_meter_year
      common.py               B1
      ev.py                   B2
      heatpump.py             B3
      pv.py                   B4
      battery.py              B5
      build.py                B6
    events/
      __init__.py
      ev_sessions.py          T0-4 (signature) + C1
      pv_windows.py           C2
      high_load.py            C3
      showcase.py             C3
      hp_heating.py           C6
      battery_cycles.py       C6
      run.py                  C3 (+C6)
    labels/
      __init__.py
      build.py                D1
    models/
      __init__.py
      baseline.py             D2
      train.py                D2 (+D3 calibration, +D5 second stage)
      explain.py              D4
      reasons.py              D4
      predict.py              D5
    export/
      __init__.py
      schema.py               T0-5
      build_json.py           C4
      curate.py               C4
    api/
      __init__.py
      app.py                  C7
    synth/
      __init__.py
      generate.py             T0-6
      loader.py               T0-6   read one synth meter/PLZ back as LASTGANG / hourly weather frames (tests, Streams B and C)
      weather.py              T0-6
      profiles.py             T0-6
  tests/
    conftest.py               T0-6
    test_config.py            T0-2
    test_store.py             T0-3
    test_features_base.py     T0-4
    test_export_schema.py     T0-5
    test_synth.py             T0-6
    test_cli.py               T0-7
    test_preview_data.py      (existing, kept)
    test_check_data.py        A1
    test_registry.py          A2
    test_lastgang.py          A3
    test_weather.py           A4
    test_features_common.py   B1
    test_features_ev.py       B2
    test_features_heatpump.py B3
    test_features_pv.py       B4
    test_features_battery.py  B5
    test_features_build.py    B6
    test_events_ev.py         C1
    test_events_pv.py         C2
    test_events_showcase.py   C3
    test_export_json.py       C4
    test_events_hp_battery.py C6
    test_api.py               C7
    test_labels.py            D1
    test_train.py             D2, D3, D5
    test_explain.py           D4
frontend/                     C5 (small PR)
.github/workflows/backend.yml T0-7
```

---

# Phase 0 — T0 skeleton (Steven + one agent, serial)

Branch `feat/be-skeleton`. One PR at the end of T0-8, or one PR per task if teammates are waiting — T0-1 should be merged alone first so Stream A can start A1.

### Task T0-1: uv project, gitignore, CI-ready layout

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/src/osnova/__init__.py`, `backend/src/osnova/{io,features,events,labels,models,export,api,synth}/__init__.py`
- Modify: `.gitignore` (root)
- Delete: `1/1.py`

**Interfaces:**
- Produces: importable package `osnova`, console script `osnova`, dev tools `pytest`, `ruff`.

- [ ] **Step 1: Replace `backend/pyproject.toml`**

```toml
[project]
name = "osnova"
version = "0.1.0"
description = "OSNOVA prediction engine — energy-asset fingerprints from 15-minute smart-meter data"
requires-python = ">=3.11"
dependencies = [
  "polars>=1.30",
  "pyarrow>=19",
  "numpy>=2.0",
  "scikit-learn>=1.6",
  "lightgbm>=4.6",
  "shap>=0.47",
  "pydantic>=2.10",
  "pydantic-settings>=2.8",
  "typer>=0.15",
  "fastexcel>=0.13",
  "xlsxwriter>=3.2",
  "fastapi>=0.115",
  "uvicorn>=0.34",
]

[project.scripts]
osnova = "osnova.cli:app"

[dependency-groups]
dev = ["pytest>=8", "hypothesis>=6", "ruff>=0.11", "httpx>=0.28"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/osnova"]

[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "W"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create the package directories** with empty `__init__.py` files (`src/osnova/` and the eight subpackages listed above).

- [ ] **Step 3: Append to the root `.gitignore`**

```
# backend synthetic data and frontend copy of the generated JSON
backend/data/
frontend/public/data/
```

- [ ] **Step 4: Delete the stray scratch file** `git rm 1/1.py`.

- [ ] **Step 5: Install and verify**

Run: `cd backend && uv sync && uv run python -c "import osnova; print('ok')" && uv run pytest -q`
Expected: `ok`, and the existing `test_preview_data.py` passes.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/src .gitignore
git commit -m "feat(backend): uv project layout for the osnova package"
```

### Task T0-2: config

**Files:**
- Create: `backend/src/osnova/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `OsnovaSettings` (env `OSNOVA_DATA_DIR`, `OSNOVA_STORE_DIR`, `OSNOVA_WEATHER_DIR`), `Config` with `.cohort`, `.ingest`, `.features`, `.events`, `.labels`; `load_config(path: Path | None) -> Config` (JSON overrides).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json
from pathlib import Path

from osnova.config import Config, OsnovaSettings, load_config


def test_settings_read_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OSNOVA_STORE_DIR", str(tmp_path / "store"))
    s = OsnovaSettings()
    assert s.store_dir == tmp_path / "store"
    assert s.out == tmp_path / "store" / "osnova"


def test_defaults_match_spec():
    cfg = Config()
    assert cfg.ingest.unit_factor == 4.0
    assert cfg.features.min_days == 300
    assert cfg.features.ev_thresholds_kw == (3.0, 5.0, 7.0, 11.0)
    assert cfg.events.ev_residual_kw == 2.5
    assert cfg.labels.unlabeled_weight == 0.5
    assert cfg.cohort.unlabeled_sample == 3000


def test_load_config_overrides(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"ingest": {"unit_factor": 1.0}}))
    cfg = load_config(p)
    assert cfg.ingest.unit_factor == 1.0
    assert cfg.features.min_days == 300
```

- [ ] **Step 2: Run it** — `uv run pytest tests/test_config.py -v` — expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/osnova/config.py
"""All tunable constants of the pipeline. Nothing numeric lives anywhere else."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ASSETS: tuple[str, ...] = ("pv", "battery", "heat_pump", "ev")
ASSET_FE_KEY: dict[str, str] = {"pv": "pv", "battery": "battery", "heat_pump": "heatPump", "ev": "ev"}
EVENT_TYPES: tuple[str, ...] = (
    "ev_charging", "pv_generation", "heat_pump_heating", "battery_cycle", "high_consumption",
)


class OsnovaSettings(BaseSettings):
    """Where things are. Read from OSNOVA_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="OSNOVA_")
    data_dir: Path = Path("data/synth/aew-data")
    weather_dir: Path = Path("data/synth/weather")
    store_dir: Path = Path("data/synth/store")

    @property
    def out(self) -> Path:
        return self.store_dir / "osnova"


class CohortConfig(BaseModel):
    unlabeled_sample: int = 3000
    seed: int = 42


class IngestConfig(BaseModel):
    unit_factor: float = 4.0  # kWh per 15 min -> kW. Set to 1.0 if check-data says values are kW.
    import_obis: str = "1-1:1.29.0*255"
    export_obis: str = "1-1:2.29.0*255"
    n_buckets: int = 64
    csv_separator: str = ";"
    date_format: str = "%d.%m.%Y"


class FeatureConfig(BaseModel):
    min_days: int = 300
    night: tuple[int, int] = (0, 6)
    morning: tuple[int, int] = (6, 10)
    midday: tuple[int, int] = (10, 16)
    evening: tuple[int, int] = (17, 22)
    pv_midday: tuple[int, int] = (11, 14)
    summer_months: tuple[int, ...] = (6, 7, 8)
    winter_months: tuple[int, ...] = (12, 1, 2)
    near_zero_kw: float = 0.05
    ev_thresholds_kw: tuple[float, ...] = (3.0, 5.0, 7.0, 11.0)
    high_load_kw: float = 3.0
    temp_bin_edges_c: tuple[float, ...] = (-5.0, 0.0, 5.0, 10.0, 15.0)
    sunny_quantile: float = 0.75
    cloudy_quantile: float = 0.25


class EventConfig(BaseModel):
    ev_baseline_window: int = 32  # intervals (8 h) centred rolling median; sessions must be < half of it
    ev_residual_kw: float = 2.5
    ev_min_intervals: int = 3
    ev_gap_merge: int = 2
    ev_plateau_cv_max: float = 0.25
    ev_known_plateaus_kw: tuple[float, ...] = (3.7, 7.0, 11.0)
    pv_export_min_kw: float = 0.1
    hp_excess_kw: float = 0.8
    hp_min_transitions: int = 3
    battery_near_zero_kw: float = 0.1
    high_load_min_intervals: int = 4
    showcase_min_confidence: float = 0.6


class LabelConfig(BaseModel):
    unlabeled_weight: float = 0.5
    registry_negative_weight: float = 1.0


class Config(BaseModel):
    cohort: CohortConfig = CohortConfig()
    ingest: IngestConfig = IngestConfig()
    features: FeatureConfig = FeatureConfig()
    events: EventConfig = EventConfig()
    labels: LabelConfig = LabelConfig()


def load_config(path: Path | None = None) -> Config:
    """Defaults, optionally overridden by a JSON file with the same nesting."""
    if path is None:
        return Config()
    return Config.model_validate(json.loads(Path(path).read_text()))
```

- [ ] **Step 4: Run** `uv run pytest tests/test_config.py -v` — expected: 3 passed.

- [ ] **Step 5: Commit** — `git add backend/src/osnova/config.py backend/tests/test_config.py && git commit -m "feat(backend): pipeline config models and settings"`

### Task T0-3: store schemas, paths, manifests, weather upsampling

**Files:**
- Create: `backend/src/osnova/io/store.py`, `backend/src/osnova/io/weather.py`
- Test: `backend/tests/test_store.py`

**Interfaces:**
- Produces: `Store(settings)` with path methods; `pl.Schema` constants `REGISTRY, LASTGANG, WEATHER, FEATURE_KEYS, LABELS, EVENTS, SHOWCASE, PREDICTIONS`; `assert_schema(df, schema, name)`; `Store.write_manifest(stage, **info)`; `upsample_15min(hourly: pl.DataFrame) -> pl.DataFrame`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_store.py
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from osnova.config import OsnovaSettings
from osnova.io.store import LASTGANG, SchemaError, Store, assert_schema
from osnova.io.weather import upsample_15min


def test_store_paths(tmp_path: Path):
    st = Store(OsnovaSettings(store_dir=tmp_path))
    assert st.lastgang_dir() == tmp_path / "osnova" / "lastgang"
    assert st.bucket_path(5) == tmp_path / "osnova" / "lastgang" / "bucket=05" / "part.parquet"
    assert st.buildings_json() == tmp_path / "osnova" / "export" / "buildings.json"


def test_assert_schema_rejects_wrong_dtype():
    df = pl.DataFrame({"meter_id": [1], "ts": [datetime(2024, 1, 1)], "plz": ["5000"],
                       "import_kw": [1.0], "export_kw": [0.0], "net_kw": [1.0], "quality": ["ok"]})
    with pytest.raises(SchemaError):
        assert_schema(df, LASTGANG, "lastgang")  # floats are f64, schema wants f32
    assert_schema(df.cast(dict(LASTGANG)), LASTGANG, "lastgang")


def test_manifest_written(tmp_path: Path):
    st = Store(OsnovaSettings(store_dir=tmp_path))
    p = st.write_manifest("ingest", rows=10)
    assert p.exists() and '"rows": 10' in p.read_text()


def test_upsample_15min_interpolates_temperature():
    hourly = pl.DataFrame({
        "plz": ["5000", "5000"],
        "ts": [datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 1)],
        "temperature_2m": [0.0, 4.0],
        "shortwave_radiation": [100.0, 200.0],
    })
    out = upsample_15min(hourly)
    assert out.height == 5  # 00:00, 00:15, 00:30, 00:45, 01:00
    assert out["temperature_2m"].to_list() == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert out["shortwave_radiation"].to_list() == [100.0, 100.0, 100.0, 100.0, 200.0]
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement `io/store.py`**

```python
# src/osnova/io/store.py
"""Paths and Parquet schemas: the contract between pipeline stages."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

import polars as pl

from osnova.config import OsnovaSettings

F32, I64, I32, STR, BOOL = pl.Float32, pl.Int64, pl.Int32, pl.String, pl.Boolean
DT = pl.Datetime("ms")

REGISTRY = pl.Schema({
    "meter_id": I64, "zaehlpunkt": STR, "gp_nr": I64, "anlage": STR, "plz": STR, "ort": STR, "kanton": STR,
    "meters_per_gp": I32, "has_pv": BOOL, "has_battery": BOOL, "has_hp": BOOL, "has_ev": BOOL,
    "has_hp_boiler": BOOL, "pv_kwp": F32, "commissioned_on": pl.Date,
})
LASTGANG = pl.Schema({
    "meter_id": I64, "ts": DT, "plz": STR, "import_kw": F32, "export_kw": F32, "net_kw": F32, "quality": STR,
})
WEATHER_VARS: tuple[str, ...] = (
    "temperature_2m", "relative_humidity_2m", "cloud_cover", "shortwave_radiation", "direct_radiation",
    "diffuse_radiation", "sunshine_duration", "precipitation", "snowfall", "wind_speed_10m",
)
WEATHER = pl.Schema({"plz": STR, "ts": DT, **{v: F32 for v in WEATHER_VARS},
                     "is_sunny_day": BOOL, "is_cloudy_day": BOOL, "hdd15": F32})
FEATURE_KEYS = pl.Schema({"meter_id": I64, "year": I32, "plz": STR, "n_days": I32})
LABELS = pl.Schema({"meter_id": I64, "year": I32, "gp_nr": I64, "asset": STR, "label": pl.Int8,
                    "weight": F32, "source": STR})
EVENTS = pl.Schema({"meter_id": I64, "type": STR, "start": DT, "end": DT, "confidence": F32,
                    "peak_kw": F32, "energy_kwh": F32})
SHOWCASE = pl.Schema({"meter_id": I64, "showcase_date": pl.Date, "n_event_types": I32})
PREDICTIONS = pl.Schema({
    "meter_id": I64, "year": I32,
    "prob_pv": F32, "prob_battery": F32, "prob_heat_pump": F32, "prob_ev": F32,
    "shap_pv": STR, "shap_battery": STR, "shap_heat_pump": STR, "shap_ev": STR,  # JSON lists
})


class SchemaError(ValueError):
    pass


def assert_schema(df: pl.DataFrame, schema: pl.Schema, name: str, *, subset: bool = False) -> None:
    """Raise SchemaError if df's columns/dtypes differ. subset=True only checks the schema's columns."""
    actual = dict(df.schema)
    for col, dtype in schema.items():
        if col not in actual:
            raise SchemaError(f"{name}: missing column {col!r}")
        if actual[col] != dtype:
            raise SchemaError(f"{name}: column {col!r} is {actual[col]}, expected {dtype}")
    if not subset:
        extra = set(actual) - set(schema)
        if extra:
            raise SchemaError(f"{name}: unexpected columns {sorted(extra)}")


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001 - not in a git checkout on Renku is fine
        return "unknown"


class Store:
    """All output paths under <store_dir>/osnova/."""

    def __init__(self, settings: OsnovaSettings):
        self.settings = settings
        self.root = settings.out

    def registry_path(self) -> Path: return self.root / "registry.parquet"
    def cohort_path(self) -> Path: return self.root / "cohort.parquet"
    def lastgang_dir(self) -> Path: return self.root / "lastgang"
    def bucket_path(self, bucket: int) -> Path: return self.lastgang_dir() / f"bucket={bucket:02d}" / "part.parquet"
    def weather_dir(self) -> Path: return self.root / "weather"
    def weather_path(self, plz: str) -> Path: return self.weather_dir() / f"plz={plz}.parquet"
    def features_path(self) -> Path: return self.root / "features.parquet"
    def features_skipped_path(self) -> Path: return self.root / "features_skipped.parquet"
    def labels_path(self) -> Path: return self.root / "labels.parquet"
    def events_path(self) -> Path: return self.root / "events.parquet"
    def showcase_path(self) -> Path: return self.root / "showcase.parquet"
    def predictions_path(self) -> Path: return self.root / "predictions.parquet"
    def models_dir(self) -> Path: return self.root / "models"
    def export_dir(self) -> Path: return self.root / "export"
    def buildings_json(self) -> Path: return self.export_dir() / "buildings.json"
    def featured_json(self) -> Path: return self.export_dir() / "featured.json"
    def data_check_json(self) -> Path: return self.root / "data_check.json"
    def logs_dir(self) -> Path: return self.root / "logs"

    def write_manifest(self, stage: str, **info: Any) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"_manifest_{stage}.json"
        payload = {"stage": stage, "git_sha": _git_sha(), "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   **{k: (str(v) if isinstance(v, Path) else v) for k, v in info.items()}}
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path


def scan_lastgang(store: Store) -> pl.LazyFrame:
    return pl.scan_parquet(store.lastgang_dir() / "bucket=*" / "part.parquet")
```

- [ ] **Step 4: Implement `io/weather.py` (T0 part only)**

```python
# src/osnova/io/weather.py
"""Weather normalisation (Stream A adds normalize_weather) and the 15-minute upsampling used by features."""
from __future__ import annotations

import polars as pl

from osnova.io.store import WEATHER_VARS

INTERPOLATED: tuple[str, ...] = ("temperature_2m",)


def upsample_15min(hourly: pl.DataFrame) -> pl.DataFrame:
    """Hourly rows of ONE plz -> 15-minute rows. Temperature linear, other columns forward-filled."""
    if hourly.height == 0:
        return hourly
    value_cols = [c for c in hourly.columns if c not in ("plz", "ts")]
    plz = hourly["plz"][0]
    grid = pl.DataFrame({"ts": pl.datetime_range(hourly["ts"].min(), hourly["ts"].max(), "15m", eager=True)})
    grid = grid.with_columns(ts=pl.col("ts").cast(hourly.schema["ts"]))
    out = grid.join(hourly.drop("plz"), on="ts", how="left").sort("ts")
    exprs = [
        pl.col(c).interpolate() if c in INTERPOLATED else pl.col(c).forward_fill() for c in value_cols
    ]
    return out.with_columns(exprs).with_columns(plz=pl.lit(plz)).select(["plz", "ts", *value_cols])


__all__ = ["WEATHER_VARS", "upsample_15min"]
```

- [ ] **Step 5: Run** `uv run pytest tests/test_store.py -v` — expected: 4 passed.

- [ ] **Step 6: Commit** — `git add backend/src/osnova/io backend/tests/test_store.py && git commit -m "contract: parquet schemas, store paths, manifests, weather upsampling"`

### Task T0-4: feature base (MeterYear, registry) and the EV-detector signature

**Files:**
- Create: `backend/src/osnova/features/base.py`, `backend/src/osnova/events/ev_sessions.py` (signature only)
- Test: `backend/tests/test_features_base.py`

**Interfaces:**
- Produces:
  - `MeterYear(meter_id: int, year: int, plz: str, df: pl.DataFrame)`; `df` columns: `ts, import_kw, export_kw, net_kw, quality, hour (Int8), minute_of_day (Int16), month (Int8), is_weekend (Bool), daypart (String: night|morning|midday|evening|other), season (String: summer|winter|shoulder)` + all `WEATHER` value columns (nullable) .
  - `feature_group(name: str)` decorator; `FeatureFn = Callable[[MeterYear, FeatureConfig], dict[str, float]]`; `run_all(my, cfg, groups: Iterable[str] | None = None) -> dict[str, float]`; `registered_groups() -> dict[str, list[FeatureFn]]`.
  - `make_meter_year(lastgang: pl.DataFrame, weather_hourly: pl.DataFrame | None, cfg: FeatureConfig) -> MeterYear` (lastgang rows of one meter and one calendar year).
  - `detect_ev_sessions(ts: np.ndarray, import_kw: np.ndarray, cfg: EventConfig) -> pl.DataFrame` with columns `start (Datetime ms), end, plateau_kw (f32), energy_kwh (f32), duration_h (f32), n_intervals (i32), confidence (f32)`. Stub raises `NotImplementedError("Stream C, card C1")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_base.py
from datetime import datetime, timedelta

import polars as pl

from osnova.config import FeatureConfig
from osnova.features.base import MeterYear, feature_group, make_meter_year, registered_groups, run_all


def _lastgang(n_days: int = 3) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    ts = [start + timedelta(minutes=15 * i) for i in range(96 * n_days)]
    return pl.DataFrame({
        "meter_id": [1] * len(ts), "ts": ts, "plz": ["5000"] * len(ts),
        "import_kw": [0.5] * len(ts), "export_kw": [0.0] * len(ts), "net_kw": [0.5] * len(ts),
        "quality": ["ok"] * len(ts),
    }).cast({"meter_id": pl.Int64, "ts": pl.Datetime("ms"), "import_kw": pl.Float32,
             "export_kw": pl.Float32, "net_kw": pl.Float32})


def _weather(n_days: int = 3) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    ts = [start + timedelta(hours=h) for h in range(24 * n_days)]
    return pl.DataFrame({"plz": ["5000"] * len(ts), "ts": ts, "temperature_2m": [float(h % 24) for h in range(len(ts))],
                         "shortwave_radiation": [0.0] * len(ts)}).cast({"ts": pl.Datetime("ms")})


def test_make_meter_year_adds_calendar_and_weather():
    my = make_meter_year(_lastgang(), _weather(), FeatureConfig())
    assert isinstance(my, MeterYear) and my.year == 2024 and my.plz == "5000"
    row = my.df.filter(pl.col("ts") == datetime(2024, 1, 1, 7, 30)).row(0, named=True)
    assert row["hour"] == 7 and row["minute_of_day"] == 450 and row["daypart"] == "morning"
    assert row["season"] == "winter" and row["is_weekend"] is False
    assert abs(row["temperature_2m"] - 7.5) < 1e-6  # interpolated between 7 and 8
    assert my.df.height == 96 * 3


def test_make_meter_year_without_weather_has_null_weather_columns():
    my = make_meter_year(_lastgang(), None, FeatureConfig())
    assert my.df["temperature_2m"].null_count() == my.df.height


def test_feature_registry_runs_group():
    @feature_group("testgroup")
    def f(my: MeterYear, cfg: FeatureConfig) -> dict[str, float]:
        return {"mean_kw": float(my.df["net_kw"].mean())}

    my = make_meter_year(_lastgang(), None, FeatureConfig())
    out = run_all(my, FeatureConfig(), groups=["testgroup"])
    assert out == {"mean_kw": 0.5}
    assert "testgroup" in registered_groups()
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement `features/base.py`**

```python
# src/osnova/features/base.py
"""MeterYear: the frame every feature function sees. Plus the feature registry."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import polars as pl

from osnova.config import FeatureConfig
from osnova.io.store import WEATHER_VARS
from osnova.io.weather import upsample_15min

FeatureFn = Callable[["MeterYear", FeatureConfig], dict[str, float]]
_REGISTRY: dict[str, list[FeatureFn]] = defaultdict(list)

CALENDAR_COLUMNS = ("hour", "minute_of_day", "month", "is_weekend", "daypart", "season")


@dataclass(frozen=True)
class MeterYear:
    meter_id: int
    year: int
    plz: str
    df: pl.DataFrame  # LASTGANG columns + CALENDAR_COLUMNS + WEATHER_VARS (+ is_sunny_day, is_cloudy_day, hdd15)


def feature_group(name: str) -> Callable[[FeatureFn], FeatureFn]:
    def register(fn: FeatureFn) -> FeatureFn:
        _REGISTRY[name].append(fn)
        return fn
    return register


def registered_groups() -> dict[str, list[FeatureFn]]:
    return dict(_REGISTRY)


def run_all(my: MeterYear, cfg: FeatureConfig, groups: Iterable[str] | None = None) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in groups if groups is not None else list(_REGISTRY):
        for fn in _REGISTRY[name]:
            out.update(fn(my, cfg))
    return out


def _daypart_expr(cfg: FeatureConfig) -> pl.Expr:
    h = pl.col("hour")
    return (
        pl.when((h >= cfg.night[0]) & (h < cfg.night[1])).then(pl.lit("night"))
        .when((h >= cfg.morning[0]) & (h < cfg.morning[1])).then(pl.lit("morning"))
        .when((h >= cfg.midday[0]) & (h < cfg.midday[1])).then(pl.lit("midday"))
        .when((h >= cfg.evening[0]) & (h < cfg.evening[1])).then(pl.lit("evening"))
        .otherwise(pl.lit("other"))
    )


def _season_expr(cfg: FeatureConfig) -> pl.Expr:
    m = pl.col("month")
    return (
        pl.when(m.is_in(list(cfg.summer_months))).then(pl.lit("summer"))
        .when(m.is_in(list(cfg.winter_months))).then(pl.lit("winter"))
        .otherwise(pl.lit("shoulder"))
    )


def add_calendar(df: pl.DataFrame, cfg: FeatureConfig) -> pl.DataFrame:
    ts = pl.col("ts")
    return df.with_columns(
        hour=ts.dt.hour().cast(pl.Int8),
        minute_of_day=(ts.dt.hour().cast(pl.Int16) * 60 + ts.dt.minute().cast(pl.Int16)),
        month=ts.dt.month().cast(pl.Int8),
        is_weekend=ts.dt.weekday() >= 6,
    ).with_columns(daypart=_daypart_expr(cfg), season=_season_expr(cfg))


def make_meter_year(lastgang: pl.DataFrame, weather_hourly: pl.DataFrame | None, cfg: FeatureConfig) -> MeterYear:
    """Rows of one meter and one calendar year -> MeterYear with calendar and weather columns."""
    df = add_calendar(lastgang.sort("ts"), cfg)
    weather_cols = [*WEATHER_VARS, "is_sunny_day", "is_cloudy_day", "hdd15"]
    if weather_hourly is not None and weather_hourly.height > 0:
        w = upsample_15min(weather_hourly).drop("plz")
        df = df.join(w, on="ts", how="left")
    missing = [c for c in weather_cols if c not in df.columns]
    df = df.with_columns([pl.lit(None, dtype=pl.Boolean if c.startswith("is_") else pl.Float32).alias(c)
                          for c in missing])
    first = df.row(0, named=True)
    return MeterYear(meter_id=int(first["meter_id"]), year=int(first["ts"].year), plz=str(first["plz"]), df=df)
```

- [ ] **Step 4: Create the detector signature `events/ev_sessions.py`**

```python
# src/osnova/events/ev_sessions.py
"""EV charging session detector. Shared by the EV features (Stream B) and the event export (Stream C)."""
from __future__ import annotations

import numpy as np
import polars as pl

from osnova.config import EventConfig

SESSION_SCHEMA = pl.Schema({
    "start": pl.Datetime("ms"), "end": pl.Datetime("ms"), "plateau_kw": pl.Float32, "energy_kwh": pl.Float32,
    "duration_h": pl.Float32, "n_intervals": pl.Int32, "confidence": pl.Float32,
})


def empty_sessions() -> pl.DataFrame:
    return pl.DataFrame(schema=SESSION_SCHEMA)


def detect_ev_sessions(ts: np.ndarray, import_kw: np.ndarray, cfg: EventConfig) -> pl.DataFrame:
    """ts: datetime64[ms] sorted, import_kw: float32 same length. Returns SESSION_SCHEMA rows."""
    raise NotImplementedError("Stream C, card C1")
```

- [ ] **Step 5: Run** `uv run pytest tests/test_features_base.py -v` — expected: 3 passed.

- [ ] **Step 6: Commit** — `git commit -am "contract: MeterYear, feature registry and EV session detector signature"` (add the new files first).

### Task T0-5: FE export schema

**Files:**
- Create: `backend/src/osnova/export/schema.py`
- Test: `backend/tests/test_export_schema.py`

**Interfaces:**
- Produces: Pydantic models `AssetPrediction, ElectricityPoint, BuildingEvent, ShapFeature, AssetExplanation, BuildingExplanation, GroundTruth, YearPrediction, Building, BuildingsFile`; `to_fe_predictions(probs: dict[str, float]) -> AssetPrediction` (internal names → FE keys, 0–1 → 0–100 ints).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_schema.py
import json

import pytest
from pydantic import ValidationError

from osnova.export.schema import Building, BuildingsFile, to_fe_predictions

MINIMAL = {
    "id": "AG-000001", "postcode": "5000", "city": "Aarau", "canton": "AG",
    "predictions": {"pv": 92, "battery": 48, "heatPump": 31, "ev": 76},
    "electricity": [{"timestamp": "2025-06-18T00:00:00+02:00", "powerKw": -1.2}],
    "events": [{"type": "ev_charging", "start": "2025-06-18T22:15:00+02:00", "end": "2025-06-19T01:30:00+02:00",
                "confidence": 0.9}],
    "explanation": {
        "model": "LightGBM", "inputs": ["15-minute load profiles"], "additionalData": ["Open-Meteo"],
        "method": "SHAP", "methodDescription": "SHAP shows which features contributed most to the prediction.",
        "assets": {k: {"reasons": ["r"], "shap": [{"feature": "f", "contribution": 0.1}]}
                   for k in ("pv", "battery", "heatPump", "ev")},
    },
}


def test_minimal_building_validates_and_defaults():
    b = Building.model_validate(MINIMAL)
    assert b.featured is False and b.history == [] and b.groundTruth is None


def test_rejects_unknown_event_type():
    bad = json.loads(json.dumps(MINIMAL))
    bad["events"][0]["type"] = "sauna"
    with pytest.raises(ValidationError):
        Building.model_validate(bad)


def test_probabilities_are_bounded_ints():
    bad = json.loads(json.dumps(MINIMAL))
    bad["predictions"]["pv"] = 101
    with pytest.raises(ValidationError):
        Building.model_validate(bad)


def test_to_fe_predictions_maps_keys_and_scales():
    p = to_fe_predictions({"pv": 0.923, "battery": 0.48, "heat_pump": 0.311, "ev": 0.76})
    assert p.model_dump() == {"pv": 92, "battery": 48, "heatPump": 31, "ev": 76}


def test_file_roundtrip():
    text = BuildingsFile.model_validate([MINIMAL]).model_dump_json()
    assert BuildingsFile.model_validate_json(text).root[0].id == "AG-000001"
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement**

```python
# src/osnova/export/schema.py
"""Mirror of frontend/src/lib/types.ts plus additive fields. Field names are camelCase on purpose."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from osnova.config import ASSET_FE_KEY

EventType = Literal["ev_charging", "pv_generation", "heat_pump_heating", "battery_cycle", "high_consumption"]
AssetKey = Literal["pv", "battery", "heatPump", "ev"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssetPrediction(_Strict):
    pv: int = Field(ge=0, le=100)
    battery: int = Field(ge=0, le=100)
    heatPump: int = Field(ge=0, le=100)  # noqa: N815 - FE key
    ev: int = Field(ge=0, le=100)


class ElectricityPoint(_Strict):
    timestamp: str  # ISO 8601 with offset
    powerKw: float  # noqa: N815 - net power, negative = export


class BuildingEvent(_Strict):
    type: EventType
    start: str
    end: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class ShapFeature(_Strict):
    feature: str
    contribution: float


class AssetExplanation(_Strict):
    reasons: list[str]
    shap: list[ShapFeature]


class BuildingExplanation(_Strict):
    model: str
    inputs: list[str]
    additionalData: list[str]  # noqa: N815
    method: str
    methodDescription: str  # noqa: N815
    assets: dict[AssetKey, AssetExplanation]


class GroundTruth(_Strict):
    pv: bool | None = None
    battery: bool | None = None
    heatPump: bool | None = None  # noqa: N815
    ev: bool | None = None


class YearPrediction(_Strict):
    year: int
    predictions: AssetPrediction


class Building(_Strict):
    id: str
    postcode: str
    city: str
    canton: str
    predictions: AssetPrediction
    electricity: list[ElectricityPoint]
    events: list[BuildingEvent]
    explanation: BuildingExplanation
    # additive fields, ignored by the FE until it opts in
    featured: bool = False
    profileDate: str | None = None  # noqa: N815
    groundTruth: GroundTruth | None = None  # noqa: N815
    history: list[YearPrediction] = Field(default_factory=list)


class BuildingsFile(RootModel[list[Building]]):
    pass


def to_fe_predictions(probs: dict[str, float]) -> AssetPrediction:
    """{'pv': 0.92, 'heat_pump': 0.31, ...} -> AssetPrediction with FE keys and 0-100 ints."""
    return AssetPrediction(**{ASSET_FE_KEY[k]: int(round(max(0.0, min(1.0, v)) * 100)) for k, v in probs.items()})
```

- [ ] **Step 4: Run** `uv run pytest tests/test_export_schema.py -v` — expected: 5 passed.

- [ ] **Step 5: Commit** — `git add backend/src/osnova/export backend/tests/test_export_schema.py && git commit -m "contract: FE buildings.json schema as pydantic models"`

### Task T0-6: synthetic data generator (real file formats) + test fixtures

The single most valuable T0 deliverable. Every later test uses it.

**Files:**
- Create: `backend/src/osnova/synth/weather.py`, `backend/src/osnova/synth/profiles.py`, `backend/src/osnova/synth/generate.py`, `backend/src/osnova/synth/loader.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_synth.py`

**Interfaces:**
- Produces:
  - `SynthSpec(meters=40, years=(2023, 2024), seed=0, plzs=("5000","5400","5105","5200","4800"), labeled_fraction=0.5)`
  - `generate(out: Path, spec: SynthSpec) -> dict` writes `out/aew-data/lastgang/<year>/<MM>/lastgang_<year>_<MM>.csv`, `out/aew-data/registry/Table2_Buildings.xlsx`, `Table3_MeterPoints.csv`, `Table4_Installations.csv`, `out/weather/open-meteo_<plz>.csv`, `out/truth.json`; returns the truth dict.
  - `synth_weather(plz, years, rng) -> pl.DataFrame` hourly with `plz, ts` + all `WEATHER_VARS`.
  - `MeterSpec` dataclass and `simulate(spec, ts, temperature, shortwave, rng) -> SimResult(import_kw, export_kw, ev_sessions)`.
  - `loader.load_synth_meter(synth_dir, meter_id, year) -> pl.DataFrame` (schema `LASTGANG`, interval-start `ts`, kW after the ×4 factor, `quality = "ok"`) and `loader.load_synth_weather(synth_dir, plz) -> pl.DataFrame` (hourly, `plz, ts` + `WEATHER_VARS` as Float32, plus `is_sunny_day`, `is_cloudy_day`, `hdd15` computed with the 75/25 % daily-radiation quantiles). Test-side helpers so Streams B and C never depend on Stream A.
  - Fixtures: `synth_dir` (session, `Path` to a generated set with 24 meters, 2023–2024), `truth` (dict), `settings` (`OsnovaSettings` pointing at `synth_dir`), `cfg` (`Config()`).
- Truth JSON shape: `{"spec": {...}, "meters": {"<meter_id>": {"gp_nr": int|null, "plz": str, "labeled": bool, "pv": bool, "battery": bool, "heat_pump": bool, "ev": bool, "pv_kwp": float, "battery_kwh": float, "ev_plateau_kw": float, "commissioned_on": "YYYY-MM-DD"|null, "has_export_row": bool}}, "ev_sessions": {"<meter_id>": [{"start": iso, "end": iso, "plateau_kw": float}]}}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synth.py
import json
from pathlib import Path

import polars as pl

EXPECTED_HEADER = "MP ID;OBIS-Code;Datum;PLZ;" + ";".join(
    f"{(i // 4) % 24:02d}:{(i % 4) * 15:02d}" for i in range(1, 97)
) + ";"


def test_lastgang_files_have_real_layout(synth_dir: Path):
    files = sorted((synth_dir / "aew-data" / "lastgang").rglob("*.csv"))
    assert len(files) == 24  # 2 years x 12 months
    first_line = files[0].read_text(encoding="utf-8").splitlines()[0]
    assert first_line == EXPECTED_HEADER  # "...;23:45;00:00;"
    df = pl.read_csv(files[6], separator=";", truncate_ragged_lines=True)  # July of year 1
    assert df["OBIS-Code"].unique().sort().to_list() == ["1-1:1.29.0*255", "1-1:2.29.0*255"]
    assert df["Datum"].str.contains(r"^\d{2}\.\d{2}\.\d{4}$").all()


def test_pv_meter_exports_at_noon_in_july(synth_dir: Path, truth: dict):
    pv_ids = [int(m) for m, t in truth["meters"].items() if t["pv"] and t["commissioned_on"] is None]
    assert pv_ids, "synth must contain PV meters commissioned before the data window"
    df = pl.read_csv(synth_dir / "aew-data" / "lastgang" / "2024" / "07" / "lastgang_2024_07.csv",
                     separator=";", truncate_ragged_lines=True)
    exp = df.filter((pl.col("MP ID") == pv_ids[0]) & (pl.col("OBIS-Code") == "1-1:2.29.0*255"))
    assert exp["12:00"].mean() > 0.05  # kWh per 15 min


def test_daily_import_energy_is_household_sized(synth_dir: Path):
    df = pl.read_csv(synth_dir / "aew-data" / "lastgang" / "2024" / "01" / "lastgang_2024_01.csv",
                     separator=";", truncate_ragged_lines=True)
    imp = df.filter(pl.col("OBIS-Code") == "1-1:1.29.0*255")
    daily = imp.select(pl.sum_horizontal(pl.exclude(["MP ID", "OBIS-Code", "Datum", "PLZ"]).cast(pl.Float64)))
    assert 3 < daily.to_series().median() < 60


def test_registry_and_weather_files(synth_dir: Path, truth: dict):
    t2 = pl.read_excel(synth_dir / "aew-data" / "registry" / "Table2_Buildings.xlsx")
    assert {"GP-Nr", "PLZ", "PV", "Ladestation für EV", "InBetrieb-Datum"} <= set(t2.columns)
    t3 = pl.read_csv(synth_dir / "aew-data" / "registry" / "Table3_MeterPoints.csv", separator=";")
    t4 = pl.read_csv(synth_dir / "aew-data" / "registry" / "Table4_Installations.csv", separator=";")
    assert t3.columns == ["MP ID", "Zählpunktbezeichnung"] and t4.columns == ["Zählpunktbezeichnung", "GPartner", "Anlage"]
    labeled = [m for m, t in truth["meters"].items() if t["labeled"]]
    assert t2.height == len(labeled)
    w = pl.read_csv(synth_dir / "weather" / "open-meteo_5000.csv")
    assert {"time", "temperature_2m", "shortwave_radiation", "sunshine_duration"} <= set(w.columns)
    assert w.height == 24 * (366 + 365)  # 2023 + 2024 (leap)


def test_truth_covers_every_asset(truth: dict):
    for asset in ("pv", "battery", "heat_pump", "ev"):
        assert any(t[asset] for t in truth["meters"].values()), asset
    assert (json.dumps(truth)) and truth["spec"]["meters"] == 24
```

- [ ] **Step 2: Write `tests/conftest.py`**

```python
# tests/conftest.py
import json
from pathlib import Path

import pytest

from osnova.config import Config, OsnovaSettings
from osnova.synth.generate import SynthSpec, generate


@pytest.fixture(scope="session")
def synth_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("synth")
    generate(out, SynthSpec(meters=24, years=(2023, 2024), seed=7))
    return out


@pytest.fixture(scope="session")
def truth(synth_dir: Path) -> dict:
    return json.loads((synth_dir / "truth.json").read_text())


@pytest.fixture
def settings(synth_dir: Path, tmp_path: Path) -> OsnovaSettings:
    return OsnovaSettings(data_dir=synth_dir / "aew-data", weather_dir=synth_dir / "weather", store_dir=tmp_path / "store")


@pytest.fixture
def cfg() -> Config:
    return Config()
```

- [ ] **Step 3: Run** — expected: ImportError on `osnova.synth.generate`.

- [ ] **Step 4: Implement `synth/weather.py`**

```python
# src/osnova/synth/weather.py
"""Plausible hourly weather for one PLZ: seasonal + diurnal temperature, clear-sky radiation x daily clearness."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import polars as pl

from osnova.io.store import WEATHER_VARS


def synth_weather(plz: str, years: tuple[int, ...], rng: np.random.Generator) -> pl.DataFrame:
    start, end = datetime(min(years), 1, 1), datetime(max(years), 12, 31, 23)
    ts = pl.datetime_range(start, end, "1h", eager=True).cast(pl.Datetime("ms"))
    n = ts.len()
    hour = ts.dt.hour().to_numpy().astype(float)
    doy = ts.dt.ordinal_day().to_numpy().astype(float)
    day_index = np.arange(n) // 24
    n_days = day_index.max() + 1
    clear_day = rng.beta(2.0, 2.0, size=n_days)[day_index]          # 0 = overcast, 1 = clear
    day_offset = rng.normal(0.0, 3.0, size=n_days)[day_index]
    seasonal = 0.55 + 0.45 * np.cos((doy - 172) / 365 * 2 * np.pi)
    sun = np.clip(np.cos((hour - 12) / 24 * 2 * np.pi), 0, None) ** 1.5
    shortwave = 900 * sun * seasonal * (0.25 + 0.75 * clear_day)
    direct = shortwave * clear_day * 0.8
    temperature = (10 - 9 * np.cos((doy - 20) / 365 * 2 * np.pi) + 4 * np.sin((hour - 9) / 24 * 2 * np.pi)
                   + day_offset + rng.normal(0, 0.5, n))
    precipitation = np.where(clear_day < 0.4, rng.exponential(0.3, n), 0.0)
    cols = {
        "temperature_2m": temperature,
        "relative_humidity_2m": 55 + 30 * (1 - clear_day) + rng.normal(0, 3, n),
        "cloud_cover": 100 * (1 - clear_day),
        "shortwave_radiation": shortwave,
        "direct_radiation": direct,
        "diffuse_radiation": shortwave - direct,
        "sunshine_duration": np.where(direct > 120, 3600.0, 0.0),
        "precipitation": precipitation,
        "snowfall": np.where(temperature < 0, precipitation, 0.0),
        "wind_speed_10m": rng.gamma(2.0, 1.5, n),
    }
    assert tuple(cols) == WEATHER_VARS
    return pl.DataFrame({"plz": [plz] * n, "ts": ts, **{k: v.astype(np.float32) for k, v in cols.items()}})
```

- [ ] **Step 5: Implement `synth/profiles.py`**

```python
# src/osnova/synth/profiles.py
"""Simulate one meter's 15-minute import/export from a base load plus injected assets."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np


@dataclass(frozen=True)
class MeterSpec:
    meter_id: int
    gp_nr: int | None
    plz: str
    pv_kwp: float = 0.0          # 0 = no PV
    battery_kwh: float = 0.0     # 0 = no battery
    heat_pump: bool = False
    ev_plateau_kw: float = 0.0   # 0 = no EV
    commissioned_on: date | None = None   # assets active only from this date; None = always
    has_export_row: bool = False


@dataclass
class SimResult:
    import_kw: np.ndarray
    export_kw: np.ndarray
    ev_sessions: list[dict] = field(default_factory=list)  # {"start": datetime, "end": datetime, "plateau_kw": float}


def _bell(x: np.ndarray, center: float, width: float) -> np.ndarray:
    return np.exp(-((x - center) ** 2) / (2 * width * width))


def simulate(spec: MeterSpec, ts: np.ndarray, temperature: np.ndarray, shortwave: np.ndarray,
             rng: np.random.Generator) -> SimResult:
    """ts: datetime64[m] 15-minute grid; temperature/shortwave: same length (already 15-min)."""
    n = len(ts)
    ts_py = ts.astype("datetime64[s]").astype(datetime)
    hour_f = np.array([t.hour + t.minute / 60 for t in ts_py])
    weekend = np.array([t.weekday() >= 5 for t in ts_py])
    active = np.ones(n, dtype=bool)
    if spec.commissioned_on is not None:
        active = ts >= np.datetime64(spec.commissioned_on)

    base = 0.3 + 0.1 * rng.random(n) + 0.6 * _bell(hour_f, 7.5, 1.0) + 1.0 * _bell(hour_f, 19.0, 1.5)
    base *= np.where(weekend & (hour_f > 9) & (hour_f < 18), 1.15, 1.0)

    hp = np.zeros(n)
    if spec.heat_pump:
        hdd = np.clip(15.0 - temperature, 0, None)
        cycling = ((np.arange(n) // 2) % 2).astype(float)          # 30 min on, 30 min off
        hp = 0.25 * hdd * (0.7 + 0.6 * cycling) * active

    ev = np.zeros(n)
    sessions: list[dict] = []
    if spec.ev_plateau_kw > 0:
        n_weeks = n // (96 * 7)
        for week in range(n_weeks):
            for _ in range(rng.integers(2, 5)):
                day = rng.integers(0, 7)
                start = week * 96 * 7 + day * 96 + int(round(rng.normal(21.5, 1.2) * 4))
                duration = int(rng.integers(6, 17))
                end = min(start + duration, n)
                if start < 0 or start >= n or not active[start]:
                    continue
                ev[start:end] = spec.ev_plateau_kw + rng.normal(0, 0.1, end - start)
                sessions.append({"start": ts_py[start], "end": ts_py[min(end, n - 1)], "plateau_kw": spec.ev_plateau_kw})

    load = base + hp + ev
    gen = spec.pv_kwp * shortwave / 1000.0 * 0.85 * active if spec.pv_kwp > 0 else np.zeros(n)
    net = load - gen

    if spec.battery_kwh > 0:
        soc, p_max, charge, discharge = 0.0, spec.battery_kwh / 2, np.zeros(n), np.zeros(n)
        for i in range(n):
            if not active[i]:
                continue
            if net[i] < 0:
                c = min(-net[i], p_max, (spec.battery_kwh - soc) * 4)
                charge[i], soc = c, soc + c / 4
            elif soc > 0:
                d = min(net[i], p_max, soc * 4)
                discharge[i], soc = d, soc - d / 4
        net = net + charge - discharge

    return SimResult(import_kw=np.clip(net, 0, None).astype(np.float32),
                     export_kw=np.clip(-net, 0, None).astype(np.float32), ev_sessions=sessions)
```

- [ ] **Step 6: Implement `synth/generate.py`**

```python
# src/osnova/synth/generate.py
"""Write Tables 1-5 in the real file formats, with known injected assets, plus truth.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from osnova.io.store import WEATHER_VARS
from osnova.io.weather import upsample_15min
from osnova.synth.profiles import MeterSpec, simulate
from osnova.synth.weather import synth_weather

ORT = {"5000": "Aarau", "5400": "Baden", "5105": "Auenstein", "5200": "Brugg", "4800": "Zofingen"}
IMPORT_OBIS, EXPORT_OBIS = "1-1:1.29.0*255", "1-1:2.29.0*255"
SLOT_COLUMNS = [f"{(i // 4) % 24:02d}:{(i % 4) * 15:02d}" for i in range(1, 97)]  # 00:15 ... 23:45, 00:00


@dataclass(frozen=True)
class SynthSpec:
    meters: int = 40
    years: tuple[int, ...] = (2023, 2024)
    seed: int = 0
    plzs: tuple[str, ...] = ("5000", "5400", "5105", "5200", "4800")
    labeled_fraction: float = 0.5


def _draw_meters(spec: SynthSpec, rng: np.random.Generator) -> list[MeterSpec]:
    start = date(min(spec.years), 1, 1)
    end = date(max(spec.years), 12, 31)
    out: list[MeterSpec] = []
    n_labeled = int(spec.meters * spec.labeled_fraction)
    for i in range(spec.meters):
        labeled = i < n_labeled
        pv = rng.random() < (0.6 if labeled else 0.15)
        hp = rng.random() < (0.5 if labeled else 0.2)
        ev = rng.random() < (0.5 if labeled else 0.15)
        bat = pv and rng.random() < (0.4 if labeled else 0.3)
        if labeled and not (pv or hp or ev):
            pv = True  # registry rows always have at least one asset
        commissioned = None
        if labeled and rng.random() < 0.3:
            commissioned = start + timedelta(days=int(rng.integers(120, (end - start).days - 120)))
        out.append(MeterSpec(
            meter_id=10000 + i, gp_nr=500000 + i if labeled else None, plz=str(rng.choice(spec.plzs)),
            pv_kwp=float(rng.choice([4.0, 6.0, 8.0, 10.0])) if pv else 0.0,
            battery_kwh=float(rng.choice([5.0, 10.0])) if bat else 0.0, heat_pump=hp,
            ev_plateau_kw=float(rng.choice([3.7, 7.0, 11.0])) if ev else 0.0,
            commissioned_on=commissioned, has_export_row=pv or rng.random() < 0.2,
        ))
    return out


def _write_lastgang(out: Path, meters: list[MeterSpec], results: dict[int, tuple], ts: np.ndarray,
                    spec: SynthSpec) -> None:
    days = ts[::96].astype("datetime64[D]")
    for year in spec.years:
        for month in range(1, 13):
            mask = np.array([d.astype(object).year == year and d.astype(object).month == month for d in days])
            day_idx = np.flatnonzero(mask)
            rows: dict[str, list] = {"MP ID": [], "OBIS-Code": [], "Datum": [], "PLZ": []}
            values: list[np.ndarray] = []
            for m in meters:
                imp, exp = results[m.meter_id]
                for obis, arr in ((IMPORT_OBIS, imp), (EXPORT_OBIS, exp)):
                    if obis == EXPORT_OBIS and not m.has_export_row:
                        continue
                    for d in day_idx:
                        rows["MP ID"].append(m.meter_id)
                        rows["OBIS-Code"].append(obis)
                        rows["Datum"].append(days[d].astype(object).strftime("%d.%m.%Y"))
                        rows["PLZ"].append(m.plz)
                        values.append(arr[d * 96:(d + 1) * 96] / 4.0)  # kW -> kWh per 15 min
            block = np.vstack(values)
            df = pl.DataFrame(rows).with_columns(
                [pl.Series(col, block[:, i].astype(np.float32)) for i, col in enumerate(SLOT_COLUMNS)]
            )
            path = out / "aew-data" / "lastgang" / str(year) / f"{month:02d}" / f"lastgang_{year}_{month:02d}.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            text = df.write_csv(separator=";", float_precision=3)
            path.write_text("\n".join(line + ";" for line in text.splitlines()) + "\n", encoding="utf-8")


def _write_registry(out: Path, meters: list[MeterSpec], rng: np.random.Generator) -> None:
    reg = out / "aew-data" / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    flag = lambda b: "ja" if b else None  # noqa: E731
    labeled = [m for m in meters if m.gp_nr is not None]
    t2 = pl.DataFrame({
        "GP-Nr": [m.gp_nr for m in labeled], "PLZ": [m.plz for m in labeled],
        "Ort": [ORT.get(m.plz, m.plz) for m in labeled], "Kanton": ["AG"] * len(labeled),
        "WärmePumpe": [flag(m.heat_pump) for m in labeled], "PV": [flag(m.pv_kwp > 0) for m in labeled],
        "PV-Leistung in kWp": [m.pv_kwp or None for m in labeled],
        "Batterie/Speicher": [flag(m.battery_kwh > 0) for m in labeled],
        "Ladestation für EV": [flag(m.ev_plateau_kw > 0) for m in labeled],
        "Wärmepumpenboiler": [flag(rng.random() < 0.2) for _ in labeled],
        "Datum Unterschrift": [(m.commissioned_on - timedelta(days=90)) if m.commissioned_on else None for m in labeled],
        "geplanter Baustart": [(m.commissioned_on - timedelta(days=30)) if m.commissioned_on else None for m in labeled],
        "Übergabe": [m.commissioned_on for m in labeled],
        "InBetrieb-Datum": [m.commissioned_on for m in labeled],
    })
    t2.write_excel(reg / "Table2_Buildings.xlsx")
    zp = {m.meter_id: f"CH{m.meter_id:031d}" for m in meters}
    pl.DataFrame({"MP ID": [m.meter_id for m in meters], "Zählpunktbezeichnung": [zp[m.meter_id] for m in meters]}
                 ).write_csv(reg / "Table3_MeterPoints.csv", separator=";")
    pl.DataFrame({"Zählpunktbezeichnung": [zp[m.meter_id] for m in labeled], "GPartner": [m.gp_nr for m in labeled],
                  "Anlage": [f"A{m.gp_nr}" for m in labeled]}).write_csv(reg / "Table4_Installations.csv", separator=";")


def _write_weather(out: Path, weather: dict[str, pl.DataFrame]) -> None:
    (out / "weather").mkdir(parents=True, exist_ok=True)
    for plz, df in weather.items():
        meta = {"plz": plz, "latitude": 47.4, "longitude": 8.05, "elevation": 400.0, "utc_offset_seconds": 3600,
                "timezone": "Europe/Zurich", "timezone_abbreviation": "CET"}
        df.with_columns([pl.lit(v).alias(k) for k, v in meta.items()]).with_columns(
            time=pl.col("ts").dt.strftime("%Y-%m-%dT%H:%M")
        ).select([*meta, "time", *WEATHER_VARS]).write_csv(out / "weather" / f"open-meteo_{plz}.csv")


def generate(out: Path, spec: SynthSpec) -> dict:
    rng = np.random.default_rng(spec.seed)
    meters = _draw_meters(spec, rng)
    start, end = datetime(min(spec.years), 1, 1), datetime(max(spec.years), 12, 31, 23, 45)
    ts = pl.datetime_range(start, end, "15m", eager=True).cast(pl.Datetime("ms")).to_numpy().astype("datetime64[m]")
    weather = {plz: synth_weather(plz, spec.years, rng) for plz in spec.plzs}
    weather15 = {plz: upsample_15min(w) for plz, w in weather.items()}
    results: dict[int, tuple] = {}
    ev_sessions: dict[str, list] = {}
    for m in meters:
        w = weather15[m.plz]
        res = simulate(m, ts, w["temperature_2m"].to_numpy(), w["shortwave_radiation"].to_numpy(), rng)
        results[m.meter_id] = (res.import_kw, res.export_kw)
        ev_sessions[str(m.meter_id)] = [{"start": s["start"].isoformat(), "end": s["end"].isoformat(),
                                         "plateau_kw": s["plateau_kw"]} for s in res.ev_sessions]
    _write_lastgang(out, meters, results, ts, spec)
    _write_registry(out, meters, rng)
    _write_weather(out, weather)
    truth = {
        "spec": asdict(spec),
        "meters": {str(m.meter_id): {
            "gp_nr": m.gp_nr, "plz": m.plz, "labeled": m.gp_nr is not None, "pv": m.pv_kwp > 0,
            "battery": m.battery_kwh > 0, "heat_pump": m.heat_pump, "ev": m.ev_plateau_kw > 0,
            "pv_kwp": m.pv_kwp, "battery_kwh": m.battery_kwh, "ev_plateau_kw": m.ev_plateau_kw,
            "commissioned_on": m.commissioned_on.isoformat() if m.commissioned_on else None,
            "has_export_row": m.has_export_row} for m in meters},
        "ev_sessions": ev_sessions,
    }
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    return truth
```


- [ ] **Step 6b: Implement `synth/loader.py`** (reads the synth CSVs back; deliberately simple and separate from Stream A's ingest)

```python
# src/osnova/synth/loader.py
"""Read synthetic files back as pipeline frames, so feature/detector tests do not need the ingest stage."""
from __future__ import annotations

from pathlib import Path

import polars as pl

from osnova.io.store import LASTGANG, WEATHER_VARS
from osnova.synth.generate import EXPORT_OBIS, IMPORT_OBIS, SLOT_COLUMNS

UNIT_FACTOR = 4.0  # synth writes kWh per 15 min


def load_synth_meter(synth_dir: Path, meter_id: int, year: int) -> pl.DataFrame:
    files = sorted((synth_dir / "aew-data" / "lastgang" / str(year)).rglob("*.csv"))
    wide = pl.concat([
        pl.read_csv(f, separator=";", truncate_ragged_lines=True,
                    schema_overrides={"MP ID": pl.Int64, "PLZ": pl.String, **{s: pl.Float32 for s in SLOT_COLUMNS}})
        .select(["MP ID", "OBIS-Code", "Datum", "PLZ", *SLOT_COLUMNS]).filter(pl.col("MP ID") == meter_id)
        for f in files
    ])
    idx = {s: i for i, s in enumerate(SLOT_COLUMNS)}
    long = (wide.unpivot(index=["MP ID", "OBIS-Code", "Datum", "PLZ"], on=SLOT_COLUMNS, variable_name="slot", value_name="v")
            .with_columns(ts=pl.col("Datum").str.to_date("%d.%m.%Y").cast(pl.Datetime("ms"))
                          + pl.duration(minutes=pl.col("slot").replace_strict(idx, return_dtype=pl.Int32) * 15))
            .group_by(["MP ID", "ts", "PLZ"]).agg(
                import_kw=pl.col("v").filter(pl.col("OBIS-Code") == IMPORT_OBIS).first() * UNIT_FACTOR,
                export_kw=pl.col("v").filter(pl.col("OBIS-Code") == EXPORT_OBIS).first().fill_null(0.0) * UNIT_FACTOR)
            .with_columns(net_kw=pl.col("import_kw") - pl.col("export_kw"), quality=pl.lit("ok"))
            .rename({"MP ID": "meter_id", "PLZ": "plz"})
            .select(list(LASTGANG.keys())).cast(dict(LASTGANG)).sort("ts"))
    return long


def load_synth_weather(synth_dir: Path, plz: str) -> pl.DataFrame:
    df = pl.read_csv(synth_dir / "weather" / f"open-meteo_{plz}.csv", schema_overrides={"plz": pl.String})
    df = df.with_columns(ts=pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M").cast(pl.Datetime("ms")),
                         **{v: pl.col(v).cast(pl.Float32) for v in WEATHER_VARS})
    daily = (df.group_by(day=pl.col("ts").dt.date(), year=pl.col("ts").dt.year())
               .agg(rad=pl.col("shortwave_radiation").sum())
               .with_columns(hi=pl.col("rad").quantile(0.75).over("year"), lo=pl.col("rad").quantile(0.25).over("year"))
               .select("day", is_sunny_day=pl.col("rad") >= pl.col("hi"), is_cloudy_day=pl.col("rad") <= pl.col("lo")))
    return (df.with_columns(day=pl.col("ts").dt.date()).join(daily, on="day", how="left").drop("day")
              .with_columns(hdd15=(15.0 - pl.col("temperature_2m")).clip(lower_bound=0.0).cast(pl.Float32))
              .select(["plz", "ts", *WEATHER_VARS, "is_sunny_day", "is_cloudy_day", "hdd15"]).sort("ts"))
```

Add to `tests/test_synth.py`:

```python
def test_loader_roundtrip(synth_dir: Path, truth: dict):
    from osnova.io.store import LASTGANG, assert_schema
    from osnova.synth.loader import load_synth_meter, load_synth_weather

    mid = next(int(m) for m, t in truth["meters"].items() if t["pv"])
    lg = load_synth_meter(synth_dir, mid, 2024)
    assert_schema(lg, LASTGANG, "lastgang")
    assert lg.height == 366 * 96 and lg["export_kw"].max() > 0.5
    w = load_synth_weather(synth_dir, lg["plz"][0])
    assert {"is_sunny_day", "hdd15"} <= set(w.columns) and w.height == 24 * 366 + 24 * 365
```

- [ ] **Step 7: Run** `uv run pytest tests/test_synth.py -v` — expected: 6 passed in well under a minute. If `write_excel` complains, `uv add xlsxwriter` is already in deps; if `read_excel` complains, check `fastexcel` is installed.

- [ ] **Step 8: Commit** — `git add backend/src/osnova/synth backend/tests/conftest.py backend/tests/test_synth.py && git commit -m "feat(backend): synthetic AEW-format data generator with injected assets"`

### Task T0-7: CLI with stubs, `synth` command, CI workflow

**Files:**
- Create: `backend/src/osnova/cli.py`, `.github/workflows/backend.yml`
- Test: `backend/tests/test_cli.py`

**Interfaces:**
- Produces: typer app `osnova` with subcommands `synth`, `check-data`, `registry`, `ingest`, `weather`, `features`, `events`, `train`, `export`, `api`. Every subcommand takes `--config PATH` (JSON overrides). Stubs exit with code 2 and message `not implemented: Stream X card Y`. Later tasks replace the stub bodies in place.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from pathlib import Path

from typer.testing import CliRunner

from osnova.cli import app

runner = CliRunner()


def test_synth_command_writes_truth(tmp_path: Path):
    r = runner.invoke(app, ["synth", "--out", str(tmp_path), "--meters", "6", "--years", "2024", "--seed", "1"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "truth.json").exists()


def test_stub_exits_with_stream_hint():
    r = runner.invoke(app, ["train"])
    assert r.exit_code == 2 and "Stream D" in r.output
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement `cli.py`**

```python
# src/osnova/cli.py
"""osnova <stage> — one subcommand per pipeline stage. Stubs are replaced by the owning stream."""
from __future__ import annotations

from pathlib import Path

import typer

from osnova.config import Config, OsnovaSettings, load_config

app = typer.Typer(no_args_is_help=True, help="OSNOVA prediction engine")
ConfigOpt = typer.Option(None, "--config", help="JSON file overriding config defaults")


def _ctx(config: Path | None) -> tuple[OsnovaSettings, Config]:
    return OsnovaSettings(), load_config(config)


def _stub(stream: str, card: str) -> None:
    typer.echo(f"not implemented: {stream} card {card}", err=False)
    raise typer.Exit(code=2)


@app.command()
def synth(out: Path = typer.Option(..., "--out"), meters: int = 40,
          years: list[int] = typer.Option([2023, 2024], "--years"), seed: int = 0) -> None:
    """Generate synthetic Tables 1-5 in the real file formats (laptop development data)."""
    from osnova.synth.generate import SynthSpec, generate

    truth = generate(out, SynthSpec(meters=meters, years=tuple(years), seed=seed))
    typer.echo(f"wrote synthetic data for {len(truth['meters'])} meters to {out}")


@app.command("check-data")
def check_data(config: Path | None = ConfigOpt) -> None:
    """Measure facts about the real mount (OBIS codes, units, DST, joins, weather coverage)."""
    _stub("Stream A", "A1")


@app.command()
def registry(config: Path | None = ConfigOpt) -> None:
    """Tables 2-4 -> registry.parquet and cohort.parquet."""
    _stub("Stream A", "A2")


@app.command()
def ingest(config: Path | None = ConfigOpt, limit_files: int | None = typer.Option(None, "--limit-files")) -> None:
    """Table 1 CSVs -> lastgang/bucket=NN/part.parquet for the cohort."""
    _stub("Stream A", "A3")


@app.command()
def weather(config: Path | None = ConfigOpt) -> None:
    """Open-Meteo CSVs -> weather/plz=XXXX.parquet."""
    _stub("Stream A", "A4")


@app.command()
def features(config: Path | None = ConfigOpt, workers: int = 4) -> None:
    """lastgang + weather -> features.parquet (one row per meter-year)."""
    _stub("Stream B", "B6")


@app.command()
def events(config: Path | None = ConfigOpt, workers: int = 4) -> None:
    """lastgang -> events.parquet + showcase.parquet."""
    _stub("Stream C", "C3")


@app.command()
def train(config: Path | None = ConfigOpt) -> None:
    """features + registry -> labels, models, predictions.parquet, metrics.json."""
    _stub("Stream D", "D2")


@app.command()
def export(config: Path | None = ConfigOpt, featured: int = 10, others: int = 200) -> None:
    """Everything -> export/buildings.json."""
    _stub("Stream C", "C4")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the exported JSON over HTTP."""
    _stub("Stream C", "C7")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Create `.github/workflows/backend.yml`**

```yaml
name: backend
on:
  push:
    paths: ["backend/**", ".github/workflows/backend.yml"]
  pull_request:
    paths: ["backend/**", ".github/workflows/backend.yml"]
jobs:
  test:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { enable-cache: true }
      - run: uv python install 3.11
      - run: uv sync --all-groups
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pytest -q
```

- [ ] **Step 5: Run** `uv run pytest -q && uv run ruff check . && uv run ruff format .` — expected: all green (run `ruff format .` once to normalise the new files, then commit the formatted result).

- [ ] **Step 6: Commit** — `git add backend/src/osnova/cli.py backend/tests/test_cli.py .github/workflows/backend.yml && git commit -m "feat(backend): osnova CLI with stage stubs and CI workflow"`

### Task T0-8: docs and handover

**Files:**
- Modify: `backend/README.md` (replace the Layout and Tests sections), keep `backend/CLAUDE.md` (already committed).

- [ ] **Step 1: Rewrite the Layout/Tests sections of `backend/README.md`** so they list: the env vars `OSNOVA_DATA_DIR`, `OSNOVA_WEATHER_DIR`, `OSNOVA_STORE_DIR`; the stage order `check-data → registry → ingest → weather → features → events → train → export`; the laptop loop `uv sync`, `uv run osnova synth --out data/synth`, `uv run pytest`; the Renku loop (`git clone`, `uv sync`, export env vars, `nohup uv run osnova ingest > $OSNOVA_STORE_DIR/osnova/logs/ingest.log &`); a link to the two specs and the plan.

- [ ] **Step 2: Commit and open the T0 PR** — `git commit -am "docs: backend README for the osnova pipeline"`, push `feat/be-skeleton`, PR titled `feat(backend): pipeline skeleton, contracts, synthetic data`. Merge when CI is green. Announce in chat: "T0 merged — streams can start; rebase on main."

---

# How to run a card in Claude Code

Every card below is a self-contained prompt. To start it:

1. `git fetch && git switch -c <stream-branch> origin/main` (or rebase your stream branch) in a worktree of your own.
2. Open a fresh Claude Code session in `backend/` and paste:

```
Implement card <ID> from docs/superpowers/plans/2026-09-10-prediction-engine.md.
Read backend/CLAUDE.md and the spec section the card names first. Use TDD on synthetic data only.
When done, run `uv run ruff check . && uv run ruff format --check . && uv run pytest` and show me the output verbatim.
Do not touch files outside the card's list without asking me.
```

3. Review the diff, run `uv run pytest` yourself once, push, open a PR titled with the card ID, merge when CI is green.

Stream owners: A = Renku owner, B = ML person 1, C = FE-closest person, D = ML person 2. If only two backend people exist: one takes A+C, the other B+D, and C1 is done before anything in B.

---

# Stream A — Data on Renku (`src/osnova/io/`) — branch `feat/be-data`

Spec: design §2, §3.1–§3.4. Only Stream A runs on real data. The agent writes code and tests on synth; the human runs the stage on Renku and pastes the log back.

### Task A1: `check-data`

**Files:**
- Create: `backend/src/osnova/io/check_data.py`
- Modify: `backend/src/osnova/cli.py` (replace the `check_data` stub body)
- Test: `backend/tests/test_check_data.py`

**Interfaces:**
- Produces: `run_check(data_dir: Path, weather_dir: Path, cfg: Config, max_files: int = 3) -> dict`, `to_markdown(report: dict) -> str`.
- Report keys: `files` (count, per-year list), `obis_counts` (dict code → rows in sampled files), `unit_guess` (`"kwh_per_15min"` | `"kw"`), `daily_sum_median`, `dst_null_cells` (nulls in `02:15..03:00` on the last Sunday of March), `registry` (columns of each table, `n_gp`, `n_meters_joined`, `meters_per_gp_hist`), `weather` (files, columns, `plz_in_table1`, `plz_with_weather`, `plz_missing`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_check_data.py
from pathlib import Path

from osnova.config import Config
from osnova.io.check_data import run_check, to_markdown


def test_check_data_on_synth(synth_dir: Path, truth: dict):
    report = run_check(synth_dir / "aew-data", synth_dir / "weather", Config(), max_files=2)
    assert set(report["obis_counts"]) == {"1-1:1.29.0*255", "1-1:2.29.0*255"}
    assert report["unit_guess"] == "kwh_per_15min"
    labeled = sum(t["labeled"] for t in truth["meters"].values())
    assert report["registry"]["n_gp"] == labeled
    assert report["registry"]["n_meters_joined"] == labeled
    assert report["weather"]["plz_missing"] == []
    md = to_markdown(report)
    assert "unit_guess" in md and "1-1:2.29.0*255" in md
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement.** Find Table 1 files with `Path.rglob("*.csv*")` whose first line starts with `MP ID;OBIS-Code`. For the first `max_files` files: `pl.scan_csv(path, separator=";", truncate_ragged_lines=True, infer_schema_length=0)`; OBIS counts via `group_by("OBIS-Code").len()`; daily sums on a 2000-row sample of import rows: cast the 96 slot columns to `Float64`, `sum_horizontal`, take the median; `unit_guess = "kwh_per_15min" if median < 40 else "kw"`. DST: compute the last Sunday of March for each year present (`date(y, 3, 31) - timedelta(days=(date(y,3,31).weekday()+1) % 7)`), filter `Datum` equal to `dd.mm.yyyy` of that day, count nulls in `02:15`, `02:30`, `02:45`, `03:00`. Registry: find files by header sniffing (`GP-Nr` → Table 2, `MP ID` + `Zählpunktbezeichnung` → Table 3, `GPartner` → Table 4; read `.xlsx` with `pl.read_excel`, csv with `separator=";"`), join 3→4→2 on the raw column names and count. Weather: list `weather_dir` CSVs, read the first one's columns, collect `plz` values, compare with the PLZ set from the sampled Table 1 files. `to_markdown` renders each key as a `##` section with a fenced JSON block. CLI: `run_check(settings.data_dir, settings.weather_dir, cfg)` → write `store.data_check_json()`, print markdown.

- [ ] **Step 4: Run** `uv run pytest tests/test_check_data.py -v` — expected: PASS.

- [ ] **Step 5: Commit** `feat(backend): check-data stage`. Then the human runs on Renku: `uv run osnova check-data > check.md`, commits it as `docs/superpowers/specs/data-check-2026-09-1x.md`, posts it in chat, and sets `ingest.unit_factor` in a `config.renku.json` if the guess is `kw`.

### Task A2: `registry`

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/mapping.py` + `feature_pipeline/labels.py`; the `registry` CLI stub is retired. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/io/registry.py`
- Modify: `backend/src/osnova/cli.py` (`registry` stub)
- Test: `backend/tests/test_registry.py`

**Interfaces:**
- Produces: `find_registry_files(data_dir) -> dict[str, Path]` (keys `table2`, `table3`, `table4`, by header sniffing as in A1); `load_tables(data_dir) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]`; `meter_plz(data_dir, cfg: IngestConfig) -> pl.DataFrame` (`meter_id`, `plz`: the most frequent PLZ per meter, lazy scan of only `MP ID` and `PLZ`); `build_registry(t2, t3, t4, meter_plz) -> pl.DataFrame` (schema `REGISTRY`); `select_cohort(registry, cfg: CohortConfig) -> pl.DataFrame` (`meter_id: Int64`, `is_labeled: Boolean`). Flag rule: null, `""`, `nein`, `no`, `0`, `false` (case-insensitive, stripped) → False, anything else → True. Dates: accept Excel dates, `dd.mm.yyyy`, `yyyy-mm-dd`. `commissioned_on = coalesce(InBetrieb-Datum, Übergabe, Datum Unterschrift)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_registry.py
from datetime import date
from pathlib import Path

import polars as pl

from osnova.config import CohortConfig, IngestConfig
from osnova.io.registry import build_registry, load_tables, meter_plz, select_cohort
from osnova.io.store import REGISTRY, assert_schema


def test_registry_matches_truth(synth_dir: Path, truth: dict):
    data = synth_dir / "aew-data"
    reg = build_registry(*load_tables(data), meter_plz(data, IngestConfig()))
    assert_schema(reg, REGISTRY, "registry")
    assert reg.height == len(truth["meters"])
    for mid, t in truth["meters"].items():
        row = reg.filter(pl.col("meter_id") == int(mid)).row(0, named=True)
        assert row["plz"] == t["plz"]
        if t["labeled"]:
            assert row["gp_nr"] == t["gp_nr"] and row["has_ev"] == t["ev"] and row["has_pv"] == t["pv"]
            expected = date.fromisoformat(t["commissioned_on"]) if t["commissioned_on"] else None
            assert row["commissioned_on"] == expected
            assert row["meters_per_gp"] == 1
        else:
            assert row["gp_nr"] is None and row["has_ev"] is None


def test_cohort_has_all_labeled_and_sample(synth_dir: Path, truth: dict):
    data = synth_dir / "aew-data"
    reg = build_registry(*load_tables(data), meter_plz(data, IngestConfig()))
    cohort = select_cohort(reg, CohortConfig(unlabeled_sample=5, seed=1))
    n_labeled = sum(t["labeled"] for t in truth["meters"].values())
    assert cohort.filter(pl.col("is_labeled")).height == n_labeled
    assert cohort.filter(~pl.col("is_labeled")).height == 5
    assert select_cohort(reg, CohortConfig(unlabeled_sample=5, seed=1)).equals(cohort)  # deterministic
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement.** `meter_plz`: for each Table 1 file `pl.scan_csv(..., infer_schema_length=0).select(["MP ID", "PLZ"])`, concat, `group_by(["MP ID","PLZ"]).len()`, keep the max per meter. `build_registry`: rename raw columns to snake_case with an explicit mapping (`"GP-Nr"→gp_nr`, `"WärmePumpe"→has_hp`, `"PV"→has_pv`, `"PV-Leistung in kWp"→pv_kwp`, `"Batterie/Speicher"→has_battery`, `"Ladestation für EV"→has_ev`, `"Wärmepumpenboiler"→has_hp_boiler`, `"Ort"→ort`, `"Kanton"→kanton`), apply the flag rule with `pl.col(c).cast(pl.String).str.strip_chars().str.to_lowercase().is_in([...]).not_()` guarded by `is_null`, parse dates with `pl.coalesce([pl.col(c).cast(pl.String).str.to_date("%d.%m.%Y", strict=False), ...])` after handling already-typed date columns, join `t3 → t4` on `Zählpunktbezeichnung`, `→ t2` on `GPartner = GP-Nr`, add `meters_per_gp` via a window count over `gp_nr`, join `meter_plz` (all meters, left side), cast to `REGISTRY`. `select_cohort`: labeled = `gp_nr.is_not_null()`; unlabeled sample with `df.sample(n=min(k, height), seed=cfg.seed)` after `sort("meter_id")`. CLI writes `registry.parquet`, `cohort.parquet`, manifest with counts and join losses (meters in Table 1 not in Table 3, Table 3 rows not in Table 4, GPartner not in Table 2).

- [ ] **Step 4: Run tests** — PASS. **Step 5: Commit** `feat(backend): registry stage (tables 2-4 -> registry.parquet, cohort.parquet)`. Human runs `uv run osnova registry` on Renku and posts the manifest.

### Task A3: `ingest`

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/ingest.py`, building series under `feature_output/intermediate/by_file/`; the `ingest` CLI stub is retired. Session 1 adds the cohort filter, the OBIS import/export pivot and the unit factor. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/io/lastgang.py`
- Modify: `backend/src/osnova/cli.py` (`ingest` stub)
- Test: `backend/tests/test_lastgang.py`

**Interfaces:**
- Produces: `SLOT_COLUMNS: list[str]` (reuse `osnova.synth.generate.SLOT_COLUMNS` by import — same 96 names); `find_lastgang_files(data_dir) -> list[Path]` (sorted; header sniff `MP ID;OBIS-Code`); `scan_wide(path, cfg: IngestConfig) -> pl.LazyFrame`; `wide_to_long(lf, cfg) -> pl.LazyFrame` (columns of `LASTGANG` plus `bucket: Int32`); `dst_dates(years: Iterable[int]) -> set[date]`; `ingest(store: Store, cfg: Config, cohort_ids: list[int], limit_files: int | None = None) -> dict` (returns row counts); `scan_lastgang(store)` already exists in `io/store.py`.
- Rules: interval start `ts = Datum + 15 min × index(slot)` where `index("00:15") = 0 … index("00:00") = 95`; `import_kw = value × unit_factor`; export defaults to 0 when the meter has no export row that day; `quality = "missing"` if import is null, `"dst"` if the date is in `dst_dates`, else `"ok"`; `net_kw = import_kw − export_kw`; `bucket = meter_id % n_buckets`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lastgang.py
from datetime import date, datetime

import polars as pl

from osnova.io.lastgang import dst_dates, find_lastgang_files, ingest
from osnova.io.registry import build_registry, load_tables, meter_plz, select_cohort
from osnova.io.store import LASTGANG, Store, assert_schema, scan_lastgang


def test_dst_dates():
    assert dst_dates([2024]) == {date(2024, 3, 31), date(2024, 10, 27)}


def test_ingest_synth(settings, cfg, truth):
    data = settings.data_dir
    reg = build_registry(*load_tables(data), meter_plz(data, cfg.ingest))
    cohort = select_cohort(reg, cfg.cohort)
    store = Store(settings)
    counts = ingest(store, cfg, cohort["meter_id"].to_list(), limit_files=None)
    lf = scan_lastgang(store)
    df = lf.collect()
    assert_schema(df, LASTGANG, "lastgang")
    n_meters = cohort.height
    assert df.height == n_meters * (365 + 366) * 96
    assert counts["files"] == 24
    pv = next(int(m) for m, t in truth["meters"].items() if t["pv"] and t["commissioned_on"] is None)
    noon = df.filter((pl.col("meter_id") == pv) & (pl.col("ts") == datetime(2024, 7, 10, 12, 0))).row(0, named=True)
    assert noon["export_kw"] > 0.5 and abs(noon["net_kw"] - (noon["import_kw"] - noon["export_kw"])) < 1e-5
    first = df.filter(pl.col("meter_id") == pv).sort("ts").row(0, named=True)
    assert first["ts"] == datetime(2023, 1, 1, 0, 0)  # column "00:15" -> interval start 00:00
    assert df.filter(pl.col("ts").dt.date() == date(2024, 3, 31))["quality"].unique().to_list() == ["dst"]


def test_ingest_limit_files(settings, cfg):
    data = settings.data_dir
    reg = build_registry(*load_tables(data), meter_plz(data, cfg.ingest))
    ids = select_cohort(reg, cfg.cohort)["meter_id"].to_list()
    store = Store(settings)
    ingest(store, cfg, ids, limit_files=1)
    months = scan_lastgang(store).select(pl.col("ts").dt.month().unique()).collect()
    assert months.height == 1 and len(find_lastgang_files(data)) == 24
```

- [ ] **Step 2: Run** — expected: ImportError.

- [ ] **Step 3: Implement.** `scan_wide`: `pl.scan_csv(path, separator=cfg.csv_separator, truncate_ragged_lines=True, schema_overrides={"MP ID": pl.Int64, "OBIS-Code": pl.String, "Datum": pl.String, "PLZ": pl.String, **{s: pl.Float32 for s in SLOT_COLUMNS}}, null_values=[""])` then `.select(["MP ID", "OBIS-Code", "Datum", "PLZ", *SLOT_COLUMNS])` (drops the unnamed trailing column). `wide_to_long`:

```python
slot_index = {s: i for i, s in enumerate(SLOT_COLUMNS)}
long = (lf.filter(pl.col("MP ID").is_in(cohort_ids) & pl.col("OBIS-Code").is_in([cfg.import_obis, cfg.export_obis]))
          .unpivot(index=["MP ID", "OBIS-Code", "Datum", "PLZ"], on=SLOT_COLUMNS, variable_name="slot", value_name="value")
          .with_columns(
              date=pl.col("Datum").str.to_date(cfg.date_format),
              idx=pl.col("slot").replace_strict(slot_index, return_dtype=pl.Int32))
          .with_columns(ts=pl.col("date").cast(pl.Datetime("ms")) + pl.duration(minutes=pl.col("idx") * 15))
          .group_by(["MP ID", "ts", "PLZ", "date"]).agg(
              import_raw=pl.col("value").filter(pl.col("OBIS-Code") == cfg.import_obis).first(),
              export_raw=pl.col("value").filter(pl.col("OBIS-Code") == cfg.export_obis).first())
          .with_columns(
              import_kw=(pl.col("import_raw") * cfg.unit_factor).cast(pl.Float32),
              export_kw=(pl.col("export_raw").fill_null(0.0) * cfg.unit_factor).cast(pl.Float32))
          .with_columns(net_kw=(pl.col("import_kw") - pl.col("export_kw")).cast(pl.Float32),
                        quality=pl.when(pl.col("import_kw").is_null()).then(pl.lit("missing"))
                                  .when(pl.col("date").is_in(sorted(dst))).then(pl.lit("dst")).otherwise(pl.lit("ok")),
                        bucket=(pl.col("MP ID") % cfg.n_buckets).cast(pl.Int32))
          .rename({"MP ID": "meter_id", "PLZ": "plz"})
          .select(["meter_id", "ts", "plz", "import_kw", "export_kw", "net_kw", "quality", "bucket"]))
```

`ingest`: for each file (respecting `limit_files`), `wide_to_long(scan_wide(f)).collect(streaming=True)` and `df.write_parquet(store.lastgang_dir() / "parts", partition_by=["bucket"], mkdir=True, ...)` using a per-file name (`use_pyarrow=False`; if polars' `partition_by` cannot name files per call, write `parts/bucket=NN/<file_stem>.parquet` with a loop over `df.partition_by("bucket", as_dict=True)`). After all files: for each bucket, `pl.scan_parquet(parts/bucket=NN/*.parquet).sort(["meter_id","ts"]).drop("bucket").sink_parquet(store.bucket_path(NN))`, then delete `parts/`. Write a manifest with `files`, `rows`, `meters`, `date_min`, `date_max`. CLI: read `cohort.parquet`, call `ingest`, print the counts.

- [ ] **Step 4: Run tests** — PASS. **Step 5: Commit** `feat(backend): ingest stage (table 1 csv -> lastgang parquet buckets)`. Human on Renku: `uv run osnova ingest --limit-files 1` → check the manifest and one PV meter's July noon export; then `nohup uv run osnova ingest > $OSNOVA_STORE_DIR/osnova/logs/ingest.log 2>&1 &`.

### Task A4: `weather`

**Files:**
- Modify: `backend/src/osnova/io/weather.py` (add functions; keep `upsample_15min`)
- Modify: `backend/src/osnova/cli.py` (`weather` stub)
- Test: `backend/tests/test_weather.py`

**Interfaces:**
- Produces: `find_weather_files(weather_dir) -> list[Path]`; `normalize_weather(path, cfg: FeatureConfig) -> pl.DataFrame` (schema `WEATHER`, one PLZ per file; if a file holds several PLZs, group and return per PLZ via `normalize_weather_all(paths, cfg) -> dict[str, pl.DataFrame]`); `load_weather(store, plz) -> pl.DataFrame | None`; `write_weather(store, by_plz)`.
- Rules: `time` parsed with `%Y-%m-%dT%H:%M` as local naive; `hdd15 = max(0, 15 − temperature_2m)`; `is_sunny_day` = daily sum of `shortwave_radiation` ≥ `sunny_quantile` of the daily sums within the same PLZ and year, `is_cloudy_day` ≤ `cloudy_quantile`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_weather.py
import polars as pl

from osnova.config import FeatureConfig
from osnova.io.store import WEATHER, Store, assert_schema
from osnova.io.weather import find_weather_files, load_weather, normalize_weather, write_weather


def test_normalize_weather(settings):
    files = find_weather_files(settings.weather_dir)
    assert len(files) == 5
    df = normalize_weather(files[0], FeatureConfig())
    assert_schema(df, WEATHER, "weather")
    assert df["ts"].dtype == pl.Datetime("ms") and df.height == 24 * (365 + 366)
    sunny = df.group_by(pl.col("ts").dt.date()).agg(pl.col("is_sunny_day").first())["is_sunny_day"].mean()
    assert 0.2 < sunny < 0.3
    row = df.row(0, named=True)
    assert abs(row["hdd15"] - max(0.0, 15 - row["temperature_2m"])) < 1e-5


def test_write_and_load(settings):
    store = Store(settings)
    by_plz = {f.stem.split("_")[-1]: normalize_weather(f, FeatureConfig()) for f in find_weather_files(settings.weather_dir)}
    write_weather(store, by_plz)
    assert load_weather(store, "5000") is not None and load_weather(store, "9999") is None
```

- [ ] **Step 2–5:** run (fail) → implement (`pl.read_csv`, `with_columns(ts=pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M").cast(pl.Datetime("ms")))`, cast variables to `Float32`, daily sums via `group_by(plz, ts.dt.date())`, quantiles via `over(["plz", year])`, join flags back, `select` in `WEATHER` order) → run (pass) → commit `feat(backend): weather stage`. Human runs `uv run osnova weather` on Renku, posts the PLZ coverage from the manifest.

### Task A5: Renku full run and handover (human checklist, no agent needed)

- [ ] `check-data` committed as a spec file; `config.renku.json` created if `unit_factor` ≠ 4.
- [ ] `registry` manifest posted: labeled meters, join losses, `meters_per_gp` histogram.
- [ ] `ingest` full run finished; manifest shows all files, `date_min/max`, rows ≈ meters × days × 96.
- [ ] `weather` manifest: every cohort PLZ has weather, or the missing list is posted.
- [ ] Post in chat: "Stream A handover: store/osnova has registry, cohort, lastgang/, weather/". Streams B, C, D can now run their stages on Renku.

---

# Stream B — Features (`src/osnova/features/`) — branch `feat/be-features`

> **Superseded 2026-09-11 by feature_pipeline** (Session 1). Every card in this stream is done there; nothing to implement in `src/osnova/features/`.

Spec: design §3.5. Inputs come from `osnova.synth.loader` (T0-6) so nothing here waits for Stream A. **B2 needs C1 merged.**

Shared test helper used by every B card (create in B1, `tests/helpers.py`):

```python
# tests/helpers.py
from pathlib import Path

from osnova.config import FeatureConfig
from osnova.features.base import MeterYear, make_meter_year
from osnova.synth.loader import load_synth_meter, load_synth_weather


def meter_year(synth_dir: Path, meter_id: int, year: int, cfg: FeatureConfig | None = None) -> MeterYear:
    cfg = cfg or FeatureConfig()
    lg = load_synth_meter(synth_dir, meter_id, year)
    return make_meter_year(lg, load_synth_weather(synth_dir, lg["plz"][0]), cfg)


def pick(truth: dict, **flags: bool) -> int:
    """First meter id whose truth matches all flags and was commissioned before the data window."""
    for mid, t in truth["meters"].items():
        if t["commissioned_on"] is None and all(t[k] == v for k, v in flags.items()):
            return int(mid)
    raise AssertionError(f"no synth meter with {flags}")
```

### Task B1: common features

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/features.py`. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/common.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_features_common.py`

**Interfaces:**
- Produces (group `common`): `n_days` (distinct dates with quality ok), `mean_kw`, `median_kw`, `p95_kw` (of `net_kw`), `night_baseline_kw` (p10 of `import_kw` between 01:00 and 05:00), `daily_kwh_mean` (mean over days of Σ `import_kw` / 4), `weekend_weekday_ratio` (mean import weekend ÷ weekday), `export_present` (1.0 if any `export_kw` > 0.05), `export_kwh_year` (Σ `export_kw` / 4), `share_missing` (rows with quality ≠ ok ÷ rows).
- Every feature function filters `quality == "ok"` first via `ok = my.df.filter(pl.col("quality") == "ok")`; missing weather never raises (use `null`-tolerant polars aggregations and return `float("nan")` when empty).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_common.py
import math

from osnova.config import FeatureConfig
from osnova.features import common  # noqa: F401 - registers the group
from osnova.features.base import run_all
from tests.helpers import meter_year, pick


def test_common_features_on_pv_and_plain_meters(synth_dir, truth):
    pv = run_all(meter_year(synth_dir, pick(truth, pv=True), 2024), FeatureConfig(), groups=["common"])
    plain = run_all(meter_year(synth_dir, pick(truth, pv=False, heat_pump=False, ev=False), 2024), FeatureConfig(),
                    groups=["common"])
    assert pv["n_days"] == 366 - 1  # DST day excluded
    assert pv["export_present"] == 1.0 and pv["export_kwh_year"] > 500
    assert plain["export_present"] == 0.0 and plain["export_kwh_year"] == 0.0
    assert 0.2 < plain["night_baseline_kw"] < 0.6
    assert 3 < plain["daily_kwh_mean"] < 40
    assert plain["share_missing"] < 0.01 and not math.isnan(plain["p95_kw"])
```

- [ ] **Step 2–5:** run (fail) → implement one function per feature (or one function returning the whole dict; the registry allows both) → run (pass) → commit `feat(backend): common features`.

### Task B2: EV features (needs C1 merged)

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/features.py` + `sessions.py` (its own session detector; C1 stays the event detector). Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/ev.py`
- Test: `backend/tests/test_features_ev.py`

**Interfaces:**
- Consumes: `detect_ev_sessions(ts, import_kw, cfg: EventConfig)` from `osnova.events.ev_sessions` (C1). Feature functions receive `FeatureConfig`; construct `EventConfig()` inside `ev.py` from `osnova.config` defaults (Stream B does not change it).
- Produces (group `ev`): `count_events_above_3kw`, `…_5kw`, `…_7kw`, `…_11kw` (intervals with `import_kw` ≥ threshold), `median_consumption`, `p95_consumption`, `p99_consumption`, `max_consumption` (of `import_kw`), ramps from `diff = import_kw.diff()`: `max_positive_ramp`, `max_negative_ramp` (most negative), `p95_positive_ramp`, `p99_positive_ramp`, `p95_negative_ramp`, `p99_negative_ramp` (quantiles of the negative diffs' absolute values), session stats: `session_count`, `sessions_per_week` (= count ÷ (n_days/7)), `session_mean`, `session_median`, `session_std`, `session_variance`, `session_cv` (of `energy_kwh`; 0 when < 2 sessions), `session_plateau_kw_median`, `session_duration_median_h`, start shares `morning_start_ratio`, `midday_start_ratio`, `evening_start_ratio`, `night_start_ratio` (by daypart of `start`; `other` hours count toward the nearest daypart: 16:xx → evening, 22–23 → night), finish shares `morning_finish_ratio` … `night_finish_ratio`, high-load shares `morning_high_load_ratio`, `midday_high_load_ratio`, `evening_high_load_ratio`, `night_high_load_ratio` (intervals ≥ `high_load_kw` within the daypart ÷ intervals in the daypart).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_ev.py
from osnova.config import FeatureConfig
from osnova.features import ev  # noqa: F401
from osnova.features.base import run_all
from tests.helpers import meter_year, pick


def test_ev_features_separate_ev_from_plain(synth_dir, truth):
    with_ev = run_all(meter_year(synth_dir, pick(truth, ev=True), 2024), FeatureConfig(), groups=["ev"])
    without = run_all(meter_year(synth_dir, pick(truth, ev=False, heat_pump=False), 2024), FeatureConfig(), groups=["ev"])
    assert 1.5 < with_ev["sessions_per_week"] < 4.5
    assert with_ev["count_events_above_3kw"] > 100 and with_ev["evening_start_ratio"] + with_ev["night_start_ratio"] > 0.7
    assert with_ev["session_plateau_kw_median"] > 3.0
    assert without["sessions_per_week"] < 0.3 and without["p99_consumption"] < 3.5
    assert 0 <= with_ev["session_cv"] < 1.5
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): ev features`.

### Task B3: heat-pump features

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/features.py`. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/heatpump.py`
- Test: `backend/tests/test_features_heatpump.py`

**Interfaces:**
- Produces (group `heatpump`): `corr_temperature_net` (Pearson of hourly-mean `net_kw` vs `temperature_2m`), `mean_consumption_T_below_-5`, `mean_consumption_T_-5_to_0`, `mean_consumption_T_0_to_5`, `mean_consumption_T_5_to_10`, `mean_consumption_T_10_to_15`, `mean_consumption_T_above_15` (mean `import_kw` per temperature bin; NaN if the bin is empty), `winter_night_mean_consumption`, `summer_night_mean_consumption` (mean `import_kw`, season × daypart night), `winter_summer_night_ratio`, `hdd_slope_kw_per_degc` (OLS slope of daily mean `import_kw` on daily mean `hdd15`, `numpy.polyfit(deg=1)`), `winter_cycling_autocorr` (mean of the autocorrelation of winter-night `import_kw` at lags 2, 3, 4 intervals, computed per night and averaged), `winter_daily_kwh_p90` (p90 of daily import kWh in winter months).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_heatpump.py
import math

from osnova.config import FeatureConfig
from osnova.features import heatpump  # noqa: F401
from osnova.features.base import make_meter_year, run_all
from osnova.synth.loader import load_synth_meter
from tests.helpers import meter_year, pick


def test_heatpump_features(synth_dir, truth):
    hp = run_all(meter_year(synth_dir, pick(truth, heat_pump=True), 2024), FeatureConfig(), groups=["heatpump"])
    no = run_all(meter_year(synth_dir, pick(truth, heat_pump=False, ev=False), 2024), FeatureConfig(), groups=["heatpump"])
    assert hp["hdd_slope_kw_per_degc"] > 0.1 and hp["corr_temperature_net"] < -0.3
    assert no["hdd_slope_kw_per_degc"] < 0.03
    assert hp["winter_summer_night_ratio"] > 1.5 and no["winter_summer_night_ratio"] < 1.3
    assert hp["mean_consumption_T_0_to_5"] > hp["mean_consumption_T_above_15"]


def test_missing_weather_gives_nan_not_error(synth_dir, truth):
    lg = load_synth_meter(synth_dir, pick(truth, heat_pump=True), 2024)
    out = run_all(make_meter_year(lg, None, FeatureConfig()), FeatureConfig(), groups=["heatpump"])
    assert math.isnan(out["hdd_slope_kw_per_degc"]) and math.isnan(out["corr_temperature_net"])
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): heat-pump features`.

### Task B4: PV features

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/features.py`. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/pv.py`
- Test: `backend/tests/test_features_pv.py`

**Interfaces:**
- Produces (group `pv`): `daytime_mean_power` (mean `net_kw`, midday daypart), `morning_mean_power`, `evening_mean_power`, `negative_consumption_ratio` (share of intervals with `net_kw` < 0), `negative_daytime_consumption_ratio` (same within 10–16), `total_export_kwh`, `days_with_export_ratio` (days with any `export_kw` > `pv_export_min`… use 0.1 kW), `summer_midday_mean`, `winter_midday_mean` (mean `net_kw` in `pv_midday` hours per season), `summer_vs_winter_midday_diff` (winter − summer), `corr_radiation_net` (Pearson `shortwave_radiation` vs `net_kw`), `corr_sunshine_net`, `sunny_day_midday_mean`, `cloudy_day_midday_mean` (mean `net_kw` in `pv_midday` on `is_sunny_day` / `is_cloudy_day`), `midday_dip_depth` (`night_baseline_kw` − `sunny_day_midday_mean`), `export_peak_kw_p95` (p95 of `export_kw` > 0), `export_start_hour_median` (median hour of the first export interval per exporting day).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_pv.py
from osnova.config import FeatureConfig
from osnova.features import pv  # noqa: F401
from osnova.features.base import run_all
from tests.helpers import meter_year, pick


def test_pv_features(synth_dir, truth):
    solar = run_all(meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024), FeatureConfig(), groups=["pv"])
    plain = run_all(meter_year(synth_dir, pick(truth, pv=False), 2024), FeatureConfig(), groups=["pv"])
    assert solar["negative_daytime_consumption_ratio"] > 0.1 and plain["negative_consumption_ratio"] == 0.0
    assert solar["corr_radiation_net"] < -0.5 and abs(plain["corr_radiation_net"]) < 0.25
    assert solar["midday_dip_depth"] > 1.0 and solar["summer_vs_winter_midday_diff"] > 0.5
    assert solar["days_with_export_ratio"] > 0.5 and plain["total_export_kwh"] == 0.0
    assert solar["sunny_day_midday_mean"] < solar["cloudy_day_midday_mean"]
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): pv features`.

### Task B5: battery features

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/features.py` (the out-of-fold PV probability `pv_prob` is added by `models/train.py`). Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/battery.py`
- Test: `backend/tests/test_features_battery.py`

**Interfaces:**
- Produces (group `battery`): `near_zero_interval_ratio` (share with |`net_kw`| < `near_zero_kw`), `number_of_near_zero_blocks` (runs of ≥ 2 consecutive near-zero intervals, per year), `daytime_near_zero_ratio` (10–16), `evening_near_zero_ratio` (17–22), `consumption_per_unit_solar_radiation` (mean midday `net_kw` ÷ mean midday `shortwave_radiation`, NaN without weather), `export_clipping_ratio` (sunny-day midday intervals where `export_kw` is within 5 % of that day's export max while `shortwave_radiation` is still rising ÷ sunny-day midday intervals; 0 without export), `evening_import_sunny_vs_cloudy` (mean evening `import_kw` on sunny days ÷ on cloudy days; NaN without weather), `export_delay_minutes` (median over sunny days of minutes between the first interval with `shortwave_radiation` > 50 and the first `export_kw` > 0.1; NaN if no export). The `pv_prob` feature is **not** computed here; Stream D adds it at train time (D5).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_battery.py
from osnova.config import FeatureConfig
from osnova.features import battery  # noqa: F401
from osnova.features.base import run_all
from tests.helpers import meter_year, pick


def test_battery_features(synth_dir, truth):
    bat = run_all(meter_year(synth_dir, pick(truth, pv=True, battery=True), 2024), FeatureConfig(), groups=["battery"])
    pv_only = run_all(meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024), FeatureConfig(), groups=["battery"])
    assert bat["near_zero_interval_ratio"] > pv_only["near_zero_interval_ratio"] * 2
    assert bat["evening_import_sunny_vs_cloudy"] < 0.7 < pv_only["evening_import_sunny_vs_cloudy"]
    assert bat["export_delay_minutes"] > pv_only["export_delay_minutes"] + 30
    assert bat["number_of_near_zero_blocks"] > 50
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): battery features`.

### Task B6: feature build runner + CLI (needs A3, A4 merged for the integration test)

> **Superseded 2026-09-11 by feature_pipeline:** `feature_pipeline/pipeline.py` via `scripts/build_feature_dataset.py`; the `features` CLI stub is retired. Not to be implemented.

**Files:**
- Create: `backend/src/osnova/features/build.py`, `backend/src/osnova/features/__init__.py` (import all groups so they register)
- Modify: `backend/src/osnova/cli.py` (`features` stub)
- Test: `backend/tests/test_features_build.py`

**Interfaces:**
- Produces: `iter_meter_years(store, cfg: Config, bucket: int) -> Iterator[MeterYear]` (reads one bucket, splits by meter and calendar year, skips meter-years with fewer than `min_days` ok days and records them), `build_bucket(store, cfg, bucket) -> tuple[pl.DataFrame, pl.DataFrame]` (features rows, skipped rows), `build_features(store, cfg, workers: int) -> pl.DataFrame` (ProcessPoolExecutor over buckets; writes `features.parquet` with `FEATURE_KEYS` columns first, then all feature columns sorted by name, and `features_skipped.parquet` with `meter_id, year, n_days, reason`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_build.py
import polars as pl

from osnova.config import Config
from osnova.features.build import build_features
from osnova.io.lastgang import ingest
from osnova.io.registry import build_registry, load_tables, meter_plz, select_cohort
from osnova.io.store import FEATURE_KEYS, Store, assert_schema
from osnova.io.weather import find_weather_files, normalize_weather, write_weather


def test_build_features_end_to_end(settings, truth):
    cfg = Config()
    data = settings.data_dir
    reg = build_registry(*load_tables(data), meter_plz(data, cfg.ingest))
    cohort = select_cohort(reg, cfg.cohort)
    store = Store(settings)
    ingest(store, cfg, cohort["meter_id"].to_list())
    write_weather(store, {f.stem.split("_")[-1]: normalize_weather(f, cfg.features) for f in find_weather_files(settings.weather_dir)})
    feats = build_features(store, cfg, workers=2)
    assert_schema(feats, FEATURE_KEYS, "features", subset=True)
    assert feats.height == cohort.height * 2  # two synth years, all complete
    assert {"sessions_per_week", "hdd_slope_kw_per_degc", "corr_radiation_net", "near_zero_interval_ratio", "export_present"} <= set(feats.columns)
    assert feats.filter(pl.col("year") == 2024)["n_days"].min() >= 300
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): features stage`. Human runs `uv run osnova features --workers 8` on Renku after A5.

---

# Stream C — Events, export, FE glue, API (`src/osnova/events/`, `export/`, `api/`) — branch `feat/be-events`

> **Session 3 (2026-09-11), grain `gp_nr`.** Input is the building series from `feature_output/intermediate/by_file/` and `feature_dataset.parquet`; `history: []`, `groundTruth` from labels.

Spec: design §3.6, §3.8, §3.9. **C1 is the first card of the whole Phase 1** because Stream B's EV features depend on it.

### Task C1: EV session detector

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Modify: `backend/src/osnova/events/ev_sessions.py` (replace the `NotImplementedError` body; keep the signature and `SESSION_SCHEMA`)
- Test: `backend/tests/test_events_ev.py`

**Interfaces:**
- Consumes: `EventConfig` (`ev_baseline_window = 32` intervals = 8 h, centred rolling median; a session must be shorter than half the window, or the baseline absorbs it), `ev_residual_kw`, `ev_min_intervals`, `ev_gap_merge`, `ev_plateau_cv_max`, `ev_known_plateaus_kw`.
- Produces: `detect_ev_sessions(ts: np.ndarray, import_kw: np.ndarray, cfg) -> pl.DataFrame` with `SESSION_SCHEMA`; helpers `rolling_median(x, window) -> np.ndarray`, `runs(mask) -> list[tuple[int, int]]` (start, end-exclusive), `merge_runs(runs, max_gap) -> list[tuple[int, int]]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events_ev.py
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from osnova.config import EventConfig
from osnova.events.ev_sessions import SESSION_SCHEMA, detect_ev_sessions, merge_runs, runs
from osnova.synth.loader import load_synth_meter
from tests.helpers import pick


def test_runs_and_merge():
    mask = np.array([0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1], dtype=bool)
    assert runs(mask) == [(1, 3), (5, 6), (9, 11)]
    assert merge_runs(runs(mask), max_gap=2) == [(1, 6), (9, 11)]


def test_detects_injected_sessions(synth_dir, truth):
    mid = pick(truth, ev=True)
    lg = load_synth_meter(synth_dir, mid, 2024).sort("ts")
    out = detect_ev_sessions(lg["ts"].to_numpy(), lg["import_kw"].to_numpy(), EventConfig())
    assert out.schema == SESSION_SCHEMA
    expected = [datetime.fromisoformat(s["start"]) for s in truth["ev_sessions"][str(mid)]
                if datetime.fromisoformat(s["start"]).year == 2024]
    found = out["start"].to_list()
    hits = sum(any(abs(f - e) <= timedelta(minutes=30) for f in found) for e in expected)
    assert hits / len(expected) > 0.7
    assert abs(out["plateau_kw"].median() - truth["meters"][str(mid)]["ev_plateau_kw"]) < 0.6
    assert (out["confidence"] >= 0.5).mean() > 0.7


def test_plain_meter_has_few_sessions(synth_dir, truth):
    lg = load_synth_meter(synth_dir, pick(truth, ev=False, heat_pump=False), 2024).sort("ts")
    out = detect_ev_sessions(lg["ts"].to_numpy(), lg["import_kw"].to_numpy(), EventConfig())
    assert out.height < 10


def test_constant_series_yields_empty():
    ts = pl.datetime_range(datetime(2024, 1, 1), datetime(2024, 1, 3), "15m", eager=True).to_numpy()
    out = detect_ev_sessions(ts, np.full(len(ts), 0.4, dtype=np.float32), EventConfig())
    assert out.height == 0
```

- [ ] **Step 2: Run** — expected: `NotImplementedError`.

- [ ] **Step 3: Implement**

```python
def rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    return pl.Series(x).rolling_median(window_size=window, center=True, min_samples=1).to_numpy()


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    m = np.concatenate([[0], mask.astype(np.int8), [0]])
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


def merge_runs(rs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for s, e in rs:
        if out and s - out[-1][1] <= max_gap:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def detect_ev_sessions(ts, import_kw, cfg: EventConfig) -> pl.DataFrame:
    x = np.nan_to_num(np.asarray(import_kw, dtype=np.float64))
    if len(x) < cfg.ev_min_intervals:
        return empty_sessions()
    resid = x - rolling_median(x, cfg.ev_baseline_window)
    rows = []
    for s, e in merge_runs(runs(resid >= cfg.ev_residual_kw), cfg.ev_gap_merge):
        if e - s < cfg.ev_min_intervals:
            continue
        seg = resid[s:e]
        plateau = float(np.median(seg))
        cv = float(seg.std() / plateau) if plateau > 0 else 9.0
        if cv > cfg.ev_plateau_cv_max:
            continue
        dist = min(abs(plateau - p) / p for p in cfg.ev_known_plateaus_kw)
        conf = 0.5 * (1 - cv / cfg.ev_plateau_cv_max) + 0.5 * (1 - min(dist, 1.0))
        rows.append({"start": ts[s], "end": ts[e - 1] + np.timedelta64(15, "m"), "plateau_kw": plateau,
                     "energy_kwh": float(seg.sum() / 4), "duration_h": (e - s) / 4, "n_intervals": e - s,
                     "confidence": float(np.clip(conf, 0, 1))})
    if not rows:
        return empty_sessions()
    return pl.DataFrame(rows).cast(dict(SESSION_SCHEMA))
```

- [ ] **Step 4: Run** `uv run pytest tests/test_events_ev.py -v` — PASS. If the injected-session hit rate is below 0.7, print the first ten `(expected, nearest found)` pairs before changing thresholds; the fix is usually the baseline window, not the residual threshold.

- [ ] **Step 5: Commit** `feat(backend): EV charging session detector` and **merge immediately** — Stream B waits on it.

### Task C2: PV generation windows

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/events/pv_windows.py`
- Test: `backend/tests/test_events_pv.py`

**Interfaces:**
- Produces: `detect_pv_windows(df: pl.DataFrame, night_baseline_kw: float, cfg: EventConfig) -> pl.DataFrame` where `df` has `ts, export_kw, net_kw, shortwave_radiation (nullable), is_sunny_day (nullable)` for any span of days; output columns `start, end, confidence, peak_kw, energy_kwh` (`Datetime(ms)`, `Float32`), one row per day with a window.
- Rules per day: if `export_kw.max() > pv_export_min_kw`: `start` = first interval with export > threshold, `end` = last such interval + 15 min, `peak_kw` = max export, `energy_kwh` = Σ export / 4, `confidence` = 0.9 if radiation present and Pearson(export, radiation) > 0.5 else 0.7. Otherwise, if `is_sunny_day` is true: the longest run (≥ 8 intervals, 09:00–17:00) with `net_kw < 0.5 × night_baseline_kw` becomes a window with confidence 0.5, `peak_kw` = −min(net), `energy_kwh` = Σ max(0, night_baseline − net) / 4. Days with neither produce no row.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events_pv.py
import polars as pl

from osnova.config import EventConfig, FeatureConfig
from osnova.events.pv_windows import detect_pv_windows
from tests.helpers import meter_year, pick


def test_pv_windows_on_exporting_meter(synth_dir, truth):
    my = meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024)
    out = detect_pv_windows(my.df, night_baseline_kw=0.4, cfg=EventConfig())
    july = out.filter(pl.col("start").dt.month() == 7)
    assert july.height >= 25
    assert (july["start"].dt.hour().median() <= 9) and (july["end"].dt.hour().median() >= 16)
    assert (july["confidence"] >= 0.7).all() and july["peak_kw"].mean() > 1.0


def test_no_windows_without_pv(synth_dir, truth):
    my = meter_year(synth_dir, pick(truth, pv=False), 2024, FeatureConfig())
    out = detect_pv_windows(my.df, night_baseline_kw=0.4, cfg=EventConfig())
    assert out.height < 20  # a few sunny-day false positives are acceptable
```

- [ ] **Step 2–5:** run (fail) → implement with `group_by(pl.col("ts").dt.date())` and a small per-day numpy function for the run search → run (pass) → commit `feat(backend): pv generation window detector`.

### Task C3: high-load fallback, showcase day, `events` stage

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/events/high_load.py`, `backend/src/osnova/events/showcase.py`, `backend/src/osnova/events/run.py`
- Modify: `backend/src/osnova/cli.py` (`events` stub)
- Test: `backend/tests/test_events_showcase.py`

**Interfaces:**
- Produces:
  - `detect_high_load(df: pl.DataFrame, claimed: pl.DataFrame, cfg) -> pl.DataFrame` — per day the longest run ≥ `high_load_min_intervals` with `import_kw ≥` that day's p95 and not overlapping any `claimed` interval (`start`,`end` columns); confidence 0.5; same output columns as C2.
  - `pick_showcase_day(events: pl.DataFrame, cfg) -> tuple[date, int] | None` — `events` has `type, start, confidence`; keep rows with `confidence ≥ showcase_min_confidence`; group by `start.dt.date()`; order by `n_distinct(type)` desc, `sum(confidence)` desc, date desc; return `(date, n_types)` or `None` if no rows.
  - `DETECTORS: list[Callable[[MeterFrame, Config], pl.DataFrame]]` in `run.py`, each returning `EVENTS` rows without `meter_id` (C6 appends two); `events_for_meter(meter_df: pl.DataFrame, weather: pl.DataFrame | None, cfg: Config) -> pl.DataFrame` (schema `EVENTS`); `run_events(store, cfg, workers) -> tuple[pl.DataFrame, pl.DataFrame]` writing `events.parquet` and `showcase.parquet` (fallback showcase date when no events: the meter's last date with 96 ok rows; `n_event_types = 0`).
  - EV sessions map to `type = "ev_charging"` with `peak_kw = plateau_kw`; PV windows to `pv_generation`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events_showcase.py
from datetime import date, datetime

import polars as pl

from osnova.config import Config, EventConfig
from osnova.events.showcase import pick_showcase_day
from osnova.events.run import run_events
from osnova.io.lastgang import ingest
from osnova.io.registry import build_registry, load_tables, meter_plz, select_cohort
from osnova.io.store import EVENTS, SHOWCASE, Store, assert_schema


def test_pick_showcase_prefers_distinct_types():
    ev = pl.DataFrame({
        "type": ["ev_charging", "pv_generation", "ev_charging", "high_consumption", "ev_charging"],
        "start": [datetime(2024, 6, 1, 22), datetime(2024, 6, 1, 10), datetime(2024, 6, 2, 22),
                  datetime(2024, 6, 2, 18), datetime(2024, 6, 3, 22)],
        "confidence": [0.9, 0.8, 0.95, 0.5, 0.9],
    })
    assert pick_showcase_day(ev, EventConfig()) == (date(2024, 6, 1), 2)  # 6/2's high_consumption is below 0.6
    assert pick_showcase_day(ev.head(0), EventConfig()) is None


def test_run_events_on_synth(settings, truth):
    cfg = Config()
    data = settings.data_dir
    reg = build_registry(*load_tables(data), meter_plz(data, cfg.ingest))
    cohort = select_cohort(reg, cfg.cohort)
    store = Store(settings)
    ingest(store, cfg, cohort["meter_id"].to_list())
    events, showcase = run_events(store, cfg, workers=2)
    assert_schema(events, EVENTS, "events") and assert_schema(showcase, SHOWCASE, "showcase") is None
    assert showcase.height == cohort.height
    ev_meters = {int(m) for m, t in truth["meters"].items() if t["ev"] and t["commissioned_on"] is None}
    per_meter = events.filter(pl.col("type") == "ev_charging").group_by("meter_id").len()
    assert set(per_meter.filter(pl.col("len") > 100)["meter_id"].to_list()) >= ev_meters
    both = showcase.filter(pl.col("n_event_types") >= 2)
    assert both.height > 0
```

- [ ] **Step 2–5:** run (fail) → implement (`run.py` loads each bucket with `pl.read_parquet(store.bucket_path(b))`, `partition_by("meter_id")`, loads weather per PLZ via `load_weather` and joins with `upsample_15min` as in `make_meter_year`, calls detectors, `ProcessPoolExecutor` over buckets) → run (pass) → commit `feat(backend): events stage with showcase-day selection`.

### Task C4: `buildings.json` exporter and curation

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/export/build_json.py`, `backend/src/osnova/export/curate.py`
- Modify: `backend/src/osnova/cli.py` (`export` stub)
- Test: `backend/tests/test_export_json.py`

**Interfaces:**
- Consumes: `registry.parquet`, `predictions.parquet` (`PREDICTIONS`; `shap_*` may be `"[]"` until D4), `showcase.parquet`, `events.parquet`, `lastgang/`, and optionally `osnova.models.reasons.reasons_for` (D4). Until D4 is merged, `DEFAULT_REASONS` returns `["Prediction based on the building's 15-minute load profile"]`.
- Produces:
  - `latest_predictions(preds: pl.DataFrame) -> pl.DataFrame` — one row per meter, the max `year`.
  - `history(preds, meter_id) -> list[YearPrediction]`.
  - `electricity_for_day(day_rows: pl.DataFrame, day: date) -> list[ElectricityPoint]` — 96 points, `net_kw`, ISO timestamps with the `Europe/Zurich` offset for that day (`zoneinfo`), missing intervals filled with `powerKw = 0.0`.
  - `events_for_day(events: pl.DataFrame, day: date) -> list[BuildingEvent]` — events with `start ≥ day−1 18:00` and `end > day 00:00` and `start < day+1 00:00`, sorted by start, at most 8.
  - `build_building(meter_id, reg_row, pred_row, hist, day_rows, events_day, feats_row, featured, reasons_fn) -> Building` with `id = f"AG-{meter_id:06d}"`, `city = ort or plz`, `canton = kanton or "AG"`, `groundTruth` from `has_*` (None when unlabeled), `profileDate = day.isoformat()`, `explanation.model = "LightGBM gradient-boosted trees, one per asset"`, `inputs = ["15-minute import and export load profiles"]`, `additionalData = ["Open-Meteo hourly weather per postcode"]`, `method = "SHAP"`, `methodDescription = "SHAP shows which features contributed most to the prediction."`, `assets[key].shap` parsed from the `shap_<asset>` JSON.
  - `build_buildings(store, cfg, featured_ids: list[int], other_ids: list[int], reasons_fn=DEFAULT_REASONS) -> list[Building]` and `write_buildings(store, buildings) -> Path` (validates with `BuildingsFile`, featured first).
  - `curate.pick_featured(registry, latest_preds, showcase, n=10, min_types=3, min_plz=5) -> list[int]` — candidates: labeled, `meters_per_gp == 1`, `n_event_types ≥ min_types`, agreement = number of assets with prob ≥ 0.8 and ground truth true, require ≥ 2; sort by agreement desc then Σ prob desc; pick round-robin across PLZ until `n`. `curate.pick_others(cohort_ids, exclude, n, seed) -> list[int]`. `featured.json` (`{"featured": [...], "others": [...]}`) is written once and reused on re-runs when present, so IDs can be pinned by hand.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export_json.py
import json
from datetime import date

import numpy as np
import polars as pl

from osnova.config import Config
from osnova.events.run import run_events
from osnova.export.build_json import build_buildings, electricity_for_day, write_buildings
from osnova.export.curate import pick_featured, pick_others
from osnova.export.schema import BuildingsFile
from osnova.io.lastgang import ingest
from osnova.io.registry import build_registry, load_tables, meter_plz, select_cohort
from osnova.io.store import PREDICTIONS, Store


def _fake_predictions(meter_ids: list[int], truth: dict, years=(2023, 2024)) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for m in meter_ids:
        t = truth["meters"][str(m)]
        for y in years:
            rows.append({"meter_id": m, "year": y,
                         **{f"prob_{a}": float(np.clip((0.9 if t[a] else 0.1) + rng.normal(0, 0.05), 0, 1))
                            for a in ("pv", "battery", "heat_pump", "ev")},
                         **{f"shap_{a}": "[]" for a in ("pv", "battery", "heat_pump", "ev")}})
    return pl.DataFrame(rows).cast(dict(PREDICTIONS))


def test_export_end_to_end(settings, truth):
    cfg = Config()
    data = settings.data_dir
    reg = build_registry(*load_tables(data), meter_plz(data, cfg.ingest))
    cohort = select_cohort(reg, cfg.cohort)
    store = Store(settings)
    ids = cohort["meter_id"].to_list()
    ingest(store, cfg, ids)
    run_events(store, cfg, workers=2)
    reg.write_parquet(store.registry_path())
    preds = _fake_predictions(ids, truth)
    preds.write_parquet(store.predictions_path())
    showcase = pl.read_parquet(store.showcase_path())
    featured = pick_featured(reg, preds.filter(pl.col("year") == 2024), showcase, n=3, min_types=2, min_plz=2)
    assert 1 <= len(featured) <= 3
    others = pick_others(ids, featured, n=5, seed=0)
    buildings = build_buildings(store, cfg, featured, others)
    path = write_buildings(store, buildings)
    parsed = BuildingsFile.model_validate_json(path.read_text()).root
    assert len(parsed) == len(featured) + 5 and parsed[0].featured is True
    b = parsed[0]
    assert len(b.electricity) == 96 and b.electricity[0].timestamp.endswith(("+01:00", "+02:00"))
    assert b.profileDate == b.electricity[0].timestamp[:10]
    assert b.groundTruth is not None and len(b.history) == 2
    assert all(e.type in {"ev_charging", "pv_generation", "heat_pump_heating", "battery_cycle", "high_consumption"} for e in b.events)
    assert json.loads((store.featured_json()).read_text())["featured"] == featured


def test_electricity_for_day_fills_gaps():
    rows = pl.DataFrame({"ts": [pl.datetime(2024, 3, 31, 0, 0)], "net_kw": [1.5]}).with_columns(pl.col("ts").cast(pl.Datetime("ms")))
    pts = electricity_for_day(rows, date(2024, 3, 31))
    assert len(pts) == 96 and pts[0].powerKw == 1.5 and pts[1].powerKw == 0.0
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): buildings.json export and featured curation`. CLI `export --featured 10 --others 200` writes `export/buildings.json` and `export/featured.json`, prints the featured IDs.

### Task C5: frontend glue PR (branch `feat/fe-backend-data`, in `frontend/`)

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/events.ts`, `frontend/src/lib/chart-option.ts`, `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/api.test.ts` (new), existing `chart-option.test.ts`

- [ ] **Step 1: Extend the event types** in `types.ts`:

```ts
export const EVENT_TYPES = [
  "ev_charging", "pv_generation", "heat_pump_heating", "battery_cycle", "high_consumption",
] as const;
```

- [ ] **Step 2: Add the two entries** in `events.ts` `EVENT_META`: `heat_pump_heating: { label: "Heat pump heating", color: ASSET_BY_KEY.heatPump.color }`, `battery_cycle: { label: "Battery charging / discharging", color: ASSET_BY_KEY.battery.color }`; in `chart-option.ts` add `heat_pump_heating: 0.12, battery_cycle: 0.12` to `BAND_OPACITY` and `heat_pump_heating: "#B4451F", battery_cycle: "#2B7D44"` to `BAND_LABEL_COLOR`.

- [ ] **Step 3: Replace `fetchBuildings`** in `api.ts`:

```ts
const DATA_URL = "/data/buildings.json";

export async function fetchBuildings(): Promise<Building[]> {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    if (res.ok) return (await res.json()) as Building[];
  } catch {
    /* fall through to mocks */
  }
  await new Promise((resolve) => setTimeout(resolve, MOCK_LATENCY_MS));
  return generateMockBuildings();
}
```

- [ ] **Step 4: Test** in `api.test.ts`: stub `global.fetch` to return `{ ok: true, json: async () => [fixtureBuilding] }` and assert the result is the fixture; stub a rejected fetch and assert mocks are returned. Run `npm run lint && npx vitest run`. Manually: copy a synth `buildings.json` into `frontend/public/data/` and check the drawer shows five band types.

- [ ] **Step 5: Commit** `feat(frontend): load backend buildings.json with mock fallback and two new event types`; PR to `main`.

### Task C6: heat-pump and battery event detectors

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/events/hp_heating.py`, `backend/src/osnova/events/battery_cycles.py`
- Modify: `backend/src/osnova/events/run.py` (append both to `DETECTORS`)
- Test: `backend/tests/test_events_hp_battery.py`

**Interfaces:**
- `detect_hp_heating(df: pl.DataFrame, cfg: EventConfig) -> pl.DataFrame` — `df` columns `ts, import_kw, season, temperature_2m (nullable)`; baseline = median `import_kw` of summer nights (00–06) over the frame (if no summer rows, p10 of all nights); on winter days, `excess = import_kw − baseline ≥ hp_excess_kw`; a run of excess with ≥ `hp_min_transitions` on/off transitions inside any 3 h window, or a sustained run ≥ 8 intervals between 04:00 and 10:00, becomes one event per day (first start to last end); confidence = 0.5 without temperature, else `clip(−corr(temperature, import) , 0.3, 0.9)` computed over the winter rows. Output columns as C2, type assigned by `run.py`.
- `detect_battery_cycles(df: pl.DataFrame, cfg: EventConfig) -> pl.DataFrame` — `df` columns `ts, net_kw, export_kw, shortwave_radiation (nullable), is_sunny_day (nullable)`; only days with `export_kw.max() > pv_export_min_kw` and `is_sunny_day`; morning charging = run ≥ 4 intervals with |net| < `battery_near_zero_kw` before the day's radiation maximum while radiation > 50; evening discharging = run ≥ 4 intervals with |net| < threshold between 17:00 and 23:00; each run is an event; confidence 0.6, 0.8 if both occur on the same day.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events_hp_battery.py
import polars as pl

from osnova.config import EventConfig
from osnova.events.battery_cycles import detect_battery_cycles
from osnova.events.hp_heating import detect_hp_heating
from tests.helpers import meter_year, pick


def test_hp_heating_events_in_winter(synth_dir, truth):
    hp = detect_hp_heating(meter_year(synth_dir, pick(truth, heat_pump=True), 2024).df, EventConfig())
    no = detect_hp_heating(meter_year(synth_dir, pick(truth, heat_pump=False, ev=False), 2024).df, EventConfig())
    assert hp.height >= 40 and (hp["start"].dt.month().is_in([1, 2, 12])).all()
    assert hp["confidence"].mean() > 0.5 and no.height < 10


def test_battery_cycles(synth_dir, truth):
    bat = detect_battery_cycles(meter_year(synth_dir, pick(truth, pv=True, battery=True), 2024).df, EventConfig())
    pv_only = detect_battery_cycles(meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024).df, EventConfig())
    assert bat.height >= 30 and bat.height > 3 * max(pv_only.height, 1)
    assert (bat["confidence"] >= 0.6).all()
```

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): heat-pump and battery event detectors`.

### Task C7: FastAPI (optional, first on the cut list)

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/api/app.py`
- Modify: `backend/src/osnova/cli.py` (`api` stub → `uvicorn.run(create_app(store), host=host, port=port)`)
- Test: `backend/tests/test_api.py`

**Interfaces:**
- `create_app(store: Store) -> FastAPI` with `GET /health` → `{"status": "ok", "buildings": n}`, `GET /buildings` → the JSON list, `GET /buildings/{id}` → one or 404, `GET /buildings/{id}/profile?date=YYYY-MM-DD` → `{"profileDate", "electricity", "events"}` for any date in `lastgang/` using `electricity_for_day` and `events_for_day` from C4, 404 if the meter or date is absent. CORS allowed for `http://localhost:3000`.

- [ ] **Step 1: Write the failing test** — `httpx`/`fastapi.testclient.TestClient` against a store where `buildings.json` was written by the C4 test helper; assert the four endpoints and the 404s.
- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): read-only FastAPI over the exported JSON`.

---

# Stream D — Labels and models (`src/osnova/labels/`, `models/`) — branch `feat/be-models`

> **Session 2 (2026-09-11), grain `gp_nr`.** Labels are three-valued per asset from `label_*` in `feature_dataset.parquet` (design §3.7 revised); no meter-year rows, no `GroupKFold` by `gp_nr` needed.

Spec: design §3.7. D1 and D2 need only T0; D2's unit test builds its own informative feature table so it does not wait for Stream B. The integration test in D5 needs B6.

### Task D1: labels (positive-unlabeled, commissioning dates)

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/labels/build.py`
- Test: `backend/tests/test_labels.py`

**Interfaces:**
- Produces: `ASSET_COLUMN = {"pv": "has_pv", "battery": "has_battery", "heat_pump": "has_hp", "ev": "has_ev"}`; `build_labels(registry: pl.DataFrame, meter_years: pl.DataFrame, cfg: LabelConfig) -> pl.DataFrame` (`meter_years` has `meter_id, year`; output schema `LABELS`, one row per meter-year-asset that is usable for training).
- Rules per (meter, year, asset): registry meter with flag true and (`commissioned_on` null or ≤ Jan 1 of `year`) → `label 1, weight 1, source "registry"`; flag true and `commissioned_on` > Dec 31 of `year` → `label 0, weight 1, source "registry_pre_install"`; flag true and commissioning inside the year → **no row**; flag false → `label 0, weight registry_negative_weight, source "registry"`; unlabeled meter (`gp_nr` null) → `label 0, weight unlabeled_weight, source "unlabeled"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_labels.py
from datetime import date

import polars as pl

from osnova.config import LabelConfig
from osnova.io.store import LABELS, REGISTRY, assert_schema
from osnova.labels.build import build_labels


def _registry() -> pl.DataFrame:
    rows = [
        # meter, gp, has_pv, has_ev, commissioned
        (1, 100, True, False, None),                 # PV always
        (2, 101, True, True, date(2024, 6, 1)),      # both commissioned mid-2024
        (3, None, None, None, None),                 # unlabeled
    ]
    df = pl.DataFrame({
        "meter_id": [r[0] for r in rows], "zaehlpunkt": ["z"] * 3, "gp_nr": [r[1] for r in rows], "anlage": ["a"] * 3,
        "plz": ["5000"] * 3, "ort": ["Aarau"] * 3, "kanton": ["AG"] * 3, "meters_per_gp": [1] * 3,
        "has_pv": [r[2] for r in rows], "has_battery": [False, False, None], "has_hp": [False, False, None],
        "has_ev": [r[3] for r in rows], "has_hp_boiler": [False, False, None], "pv_kwp": [5.0, 8.0, None],
        "commissioned_on": [r[4] for r in rows],
    })
    return df.cast(dict(REGISTRY))


def test_label_rules():
    years = pl.DataFrame({"meter_id": [1, 1, 2, 2, 3], "year": [2023, 2024, 2023, 2024, 2024]}).cast({"year": pl.Int32})
    out = build_labels(_registry(), years, LabelConfig())
    assert_schema(out, LABELS, "labels")
    def get(m, y, a):
        r = out.filter((pl.col("meter_id") == m) & (pl.col("year") == y) & (pl.col("asset") == a))
        return r.row(0, named=True) if r.height else None
    assert get(1, 2024, "pv")["label"] == 1 and get(1, 2024, "pv")["weight"] == 1.0
    assert get(1, 2024, "ev")["label"] == 0 and get(1, 2024, "ev")["source"] == "registry"
    assert get(2, 2023, "pv")["label"] == 0 and get(2, 2023, "pv")["source"] == "registry_pre_install"
    assert get(2, 2024, "pv") is None and get(2, 2024, "ev") is None  # commissioned inside the year
    assert get(3, 2024, "ev")["label"] == 0 and get(3, 2024, "ev")["weight"] == 0.5 and get(3, 2024, "ev")["source"] == "unlabeled"
    assert out.filter(pl.col("meter_id") == 2)["gp_nr"].unique().to_list() == [101]
```

- [ ] **Step 2–5:** run (fail) → implement (cross-join `meter_years × ASSETS`, join registry, `pl.when` chains, filter the ambiguous rows out, cast to `LABELS`) → run (pass) → commit `feat(backend): meter-year labels with commissioning dates and PU weights`.

### Task D2: training, metrics, rule baseline, `train` stage

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/models/train.py`, `backend/src/osnova/models/baseline.py`
- Modify: `backend/src/osnova/cli.py` (`train` stub)
- Test: `backend/tests/test_train.py`

**Interfaces:**
- Produces:
  - `feature_columns(features: pl.DataFrame) -> list[str]` — every column not in `FEATURE_KEYS` and not entirely null.
  - `LGB_PARAMS = {"objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_child_samples": 20, "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 1, "verbosity": -1}`.
  - `train_one(asset, X: pl.DataFrame, y: np.ndarray, w: np.ndarray, groups: np.ndarray, n_splits=5) -> AssetModel` with fields `booster: lgb.Booster` (final model on all rows, `num_boost_round` = mean best iteration of the folds), `oof: np.ndarray`, `best_iterations: list[int]`, `feature_names: list[str]`.
  - `metrics(y, w, score, source: np.ndarray) -> dict` — `roc_auc`, `pr_auc`, `brier`, `precision_at_50`, `recall_at_50`, `precision_at_80`, `recall_at_80` for `all` rows and for `registry` rows (`source != "unlabeled"`).
  - `train_all(features, labels, cfg: Config, models_dir: Path) -> TrainResult(metrics: dict, predictions: pl.DataFrame)` — one model per asset in the order `pv, heat_pump, ev, battery`; rows for an asset are the labels rows joined to features; `scale_pos_weight` = negatives ÷ positives; groups = `gp_nr` when present else `meter_id`; saves `models/<asset>.txt`, `models/metrics.json` (model and baseline metrics side by side), `models/feature_importance.parquet` (gain); `predictions` has `PREDICTIONS` schema for **every** feature row (final booster), `shap_*` = `"[]"` (D4 fills).
  - `baseline.baseline_scores(features) -> pl.DataFrame` (`meter_id, year, base_pv, base_battery, base_heat_pump, base_ev` in 0–1): `base_pv = 0.9 if export_present else clip(0.2 + 0.5·[midday_dip_depth > 1 and corr_radiation_net < −0.4], 0, 1)`; `base_ev = 0.85 if sessions_per_week ≥ 1 and session_plateau_kw_median ≥ 3 else 0.15`; `base_heat_pump = 0.8 if hdd_slope_kw_per_degc > 0.1 else 0.15`; `base_battery = 0.7 if export_present and evening_import_sunny_vs_cloudy < 0.7 else 0.1`; missing columns count as false.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_train.py
from pathlib import Path

import numpy as np
import polars as pl

from osnova.config import Config
from osnova.io.store import FEATURE_KEYS, LABELS, PREDICTIONS, assert_schema
from osnova.models.baseline import baseline_scores
from osnova.models.train import train_all

ASSETS = ("pv", "battery", "heat_pump", "ev")


def _synthetic_table(n: int = 300, seed: int = 0) -> tuple[pl.DataFrame, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    truth = {a: rng.random(n) < 0.3 for a in ASSETS}
    feats = pl.DataFrame({
        "meter_id": np.arange(n) + 1, "year": np.full(n, 2024), "plz": ["5000"] * n, "n_days": np.full(n, 360),
        "export_present": truth["pv"].astype(float),
        "midday_dip_depth": np.where(truth["pv"], 2.0, 0.2) + rng.normal(0, 0.3, n),
        "corr_radiation_net": np.where(truth["pv"], -0.7, 0.0) + rng.normal(0, 0.1, n),
        "sessions_per_week": np.where(truth["ev"], 2.5, 0.1) + rng.normal(0, 0.4, n),
        "session_plateau_kw_median": np.where(truth["ev"], 7.0, 0.0) + rng.normal(0, 0.5, n),
        "hdd_slope_kw_per_degc": np.where(truth["heat_pump"], 0.25, 0.01) + rng.normal(0, 0.05, n),
        "evening_import_sunny_vs_cloudy": np.where(truth["battery"], 0.4, 1.0) + rng.normal(0, 0.1, n),
        "noise_a": rng.normal(size=n), "noise_b": rng.normal(size=n),
    }).cast({"meter_id": pl.Int64, "year": pl.Int32, "n_days": pl.Int32})
    rows = []
    for i in range(n):
        for a in ASSETS:
            unlabeled = i % 3 == 0
            rows.append({"meter_id": i + 1, "year": 2024, "gp_nr": None if unlabeled else 100 + i, "asset": a,
                         "label": 0 if unlabeled else int(truth[a][i]), "weight": 0.5 if unlabeled else 1.0,
                         "source": "unlabeled" if unlabeled else "registry"})
    return feats, pl.DataFrame(rows).cast(dict(LABELS))


def test_train_all_learns_synthetic_signal(tmp_path: Path):
    feats, labels = _synthetic_table()
    assert_schema(feats, FEATURE_KEYS, "features", subset=True)
    result = train_all(feats, labels, Config(), tmp_path / "models")
    for a in ASSETS:
        assert result.metrics[a]["registry"]["roc_auc"] > 0.9, a
        assert (tmp_path / "models" / f"{a}.txt").exists()
    assert_schema(result.predictions, PREDICTIONS, "predictions")
    assert result.predictions.height == feats.height
    assert (tmp_path / "models" / "metrics.json").exists()
    assert "baseline" in result.metrics["pv"]


def test_baseline_scores_shape():
    feats, _ = _synthetic_table(50)
    base = baseline_scores(feats)
    assert base.columns == ["meter_id", "year", "base_pv", "base_battery", "base_heat_pump", "base_ev"]
    assert base["base_pv"].is_between(0, 1).all()
```

- [ ] **Step 2–5:** run (fail) → implement (`sklearn.model_selection.GroupKFold`, `lgb.train` with `lgb.Dataset(X, y, weight=w)` and `callbacks=[lgb.early_stopping(50, verbose=False)]`) → run (pass) → commit `feat(backend): LightGBM training with grouped CV, metrics and rule baseline`. CLI `train`: read `features.parquet`, `registry.parquet`, build labels (D1) for the feature rows' `(meter_id, year)`, call `train_all`, write `predictions.parquet` and a manifest.

### Task D3: calibration

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Modify: `backend/src/osnova/models/train.py`
- Test: `backend/tests/test_train.py` (add)

**Interfaces:**
- `fit_calibrator(oof: np.ndarray, y, w, source) -> IsotonicRegression` fitted on registry rows only (`out_of_bounds="clip"`), saved with `joblib.dump` to `models/<asset>_calibration.joblib`; `train_all` applies it to the final predictions (`prob_<asset>` = calibrated) and records `brier_calibrated` in metrics. Raw scores are kept in `predictions.parquet` as extra columns `raw_<asset>` — **update `PREDICTIONS` in `io/store.py` in a `contract:` commit** to add the four `raw_*` Float32 columns.

- [ ] **Step 1: Add the test** — after `train_all`, `metrics[a]["registry"]["brier_calibrated"] <= metrics[a]["registry"]["brier"] + 0.01` and the joblib file exists and `prob_*` is monotone in `raw_*` (sort by raw, check `prob` non-decreasing).
- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): isotonic calibration on registry rows` (+ the `contract:` commit for the schema).

### Task D4: SHAP explanations and reasons text

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Create: `backend/src/osnova/models/explain.py`, `backend/src/osnova/models/reasons.py`
- Modify: `backend/src/osnova/models/train.py` (fill `shap_*`)
- Test: `backend/tests/test_explain.py`

**Interfaces:**
- `explain.shap_top(booster: lgb.Booster, X: pl.DataFrame, k: int = 6) -> list[list[dict]]` — `shap.TreeExplainer(booster).shap_values(X.to_numpy())` (take the positive-class array if a list is returned); per row the `k` largest |values|, each `{"feature": FEATURE_LABELS.get(name, name.replace("_", " ")), "contribution": round(tanh(value / 2), 3)}`, sorted by |contribution| desc. `train_all` stores `json.dumps(...)` per row in `shap_<asset>`.
- `reasons.FEATURE_LABELS: dict[str, str]` (human labels for every feature name in B1–B5, e.g. `"sessions_per_week": "Charging-like sessions per week"`, `"hdd_slope_kw_per_degc": "Consumption rise per °C of cold"`, `"midday_dip_depth": "Midday net-load dip"`, `"evening_import_sunny_vs_cloudy": "Evening import after sunny vs cloudy days"`).
- `reasons.reasons_for(asset: str, feats: dict[str, float], prob: float, events_day: pl.DataFrame | None) -> list[str]` — 2–3 bullets from templates; `prob ≥ 0.5` uses the "likely" templates, else "unlikely"; numbers formatted (`{sessions_per_week:.1f}`, `{ratio:.0%}`); never states the asset as fact (wording "consistent with", "no sign of"). Templates:
  - pv likely: `"Net load drops by {midday_dip_depth:.1f} kW around midday on sunny days"`, `"{days_with_export_ratio:.0%} of days export power to the grid"`, `"Consumption correlates with solar radiation (r = {corr_radiation_net:.2f})"`; unlikely: `"No midday reduction in net load"`, `"No export to the grid recorded"`.
  - battery likely: `"Evening import after sunny days is {evening_import_sunny_vs_cloudy:.0%} of cloudy days"`, `"Net load sits near zero in {near_zero_interval_ratio:.0%} of intervals"`, `"Export starts {export_delay_minutes:.0f} min after sunrise, consistent with charging first"`; unlikely: `"Evening import does not depend on the day's sunshine"`, `"Midday surplus is exported rather than stored"`.
  - heat_pump likely: `"Consumption rises {hdd_slope_kw_per_degc:.2f} kW per °C below 15 °C"`, `"Winter nights use {winter_summer_night_ratio:.1f}× the power of summer nights"`, `"Regular on/off cycling on winter nights"`; unlikely: `"Consumption barely changes with outdoor temperature"`, `"Winter and summer night loads are similar"`.
  - ev likely: `"{sessions_per_week:.1f} charging-like sessions per week, plateau ≈ {session_plateau_kw_median:.1f} kW"`, `"{evening_night_start_ratio:.0%} of sessions start in the evening or at night"`, `"Sessions last {session_duration_median_h:.1f} h on average"`; unlikely: `"No repeated high-power plateaus"`, `"Peak power stays below {p99_consumption:.1f} kW"`.
  - If `events_day` contains the asset's event type, append `"Visible on the selected day as a highlighted band"`.
  - Missing or NaN feature → skip that template.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_explain.py
import math

import polars as pl

from osnova.models.reasons import FEATURE_LABELS, reasons_for


def test_reasons_render_numbers_and_skip_nan():
    feats = {"sessions_per_week": 2.34, "session_plateau_kw_median": 7.1, "evening_night_start_ratio": 0.8,
             "session_duration_median_h": math.nan}
    out = reasons_for("ev", feats, prob=0.9, events_day=pl.DataFrame({"type": ["ev_charging"]}))
    assert any("2.3" in r and "7.1" in r for r in out)
    assert not any("nan" in r.lower() for r in out)
    assert out[-1].startswith("Visible on the selected day")
    assert len(reasons_for("ev", {}, prob=0.1, events_day=None)) >= 1


def test_feature_labels_cover_reason_templates():
    assert "sessions_per_week" in FEATURE_LABELS and "hdd_slope_kw_per_degc" in FEATURE_LABELS
```

Add to `tests/test_train.py`: after `train_all`, `json.loads(result.predictions["shap_ev"][0])` has ≤ 6 entries, all `-1 ≤ contribution ≤ 1`, sorted by absolute value descending.

- [ ] **Step 2–5:** run (fail) → implement → run (pass) → commit `feat(backend): SHAP contributions and plain-language reasons`. Tell Stream C that `osnova.models.reasons.reasons_for` exists so C4 switches from `DEFAULT_REASONS`.

### Task D5: battery second stage, integration on synth features

> **Grain: `gp_nr`, see the revision note at the top** (`meter_id` → `gp_nr`, no `year`, input `feature_output/feature_dataset.parquet`).

**Files:**
- Modify: `backend/src/osnova/models/train.py`
- Test: `backend/tests/test_train.py` (add), needs B6 merged for the integration test

**Interfaces:**
- In `train_all`, after the PV model: add column `pv_prob` to the feature table (OOF PV score for rows that had PV labels, final-model PV prediction for the rest) before training `battery`; `pv_prob` is listed in `FEATURE_LABELS` as `"Estimated PV probability"`.
- Integration test: run `ingest`, `write_weather`, `build_features`, `build_labels`, `train_all` on the synth fixture and assert every asset's registry ROC-AUC > 0.85 (synth is easy; this catches wiring), and `pv_prob` appears in the battery model's `feature_names`.

- [ ] **Step 1–5:** test (fail) → implement → test (pass) → commit `feat(backend): battery second stage on PV probability`.

---

# Phase 4 — Integration on Renku (everyone, Day 2 morning)

> **2026-09-11:** Session 4 runs this. Replace `uv run osnova features` with Session 1's `python3 scripts/build_feature_dataset.py …` run; `train`, `events`, `export` read `feature_output/`. The `history` example in the presentation line is dropped.

- [ ] Rebase all stream branches on `main`; merge in the order A → C1 → B → D → C.
- [ ] On Renku: `git pull && uv sync`, then `uv run osnova features --workers 8`, `uv run osnova train`, `uv run osnova events --workers 8`, `uv run osnova export --featured 10 --others 200`. Each stage's manifest is posted in chat.
- [ ] Read `models/metrics.json`: registry ROC-AUC per asset next to the baseline. If an asset is below the baseline, look at `feature_importance.parquet` before touching parameters.
- [ ] Open `export/featured.json`; for each featured meter, eyeball the showcase day in the FE (copy `buildings.json` to `frontend/public/data/`). Pin or swap IDs by editing `featured.json` and re-running `export`.
- [ ] Freeze: copy the final `buildings.json` to every demo laptop; tag `main` as `demo-2026-09-1x`.
- [ ] Presentation: pipeline diagram, `check-data` facts, metrics table (model vs baseline), one SHAP summary per asset, two featured buildings, one `history` example, limitations (design §8).

# Self-review notes

- Spec coverage: §2 data facts → A1/A3; §2.3 cohort → A2; §3.1–3.4 → A1–A4; §3.5 all five groups → B1–B5, runner B6; §3.6 five detectors + showcase → C1–C3, C6; §3.7 labels/CV/calibration/SHAP/reasons/baseline/second stage → D1–D5; §3.8 export + curate + additive fields → C4; §3.9 API → C7; §5 synth → T0-6; §6 manifests → `Store.write_manifest` in every stage; §7 tests → per card; FE change → C5.
- Type consistency: `detect_ev_sessions(ts, import_kw, cfg)` is used identically in T0-4, B2, C1; `make_meter_year(lastgang, weather_hourly, cfg)` in T0-4, B1–B5, C2, C6; `Store` path methods in A3, A4, B6, C3, C4, C7; `PREDICTIONS` gains `raw_*` columns in D3 via a `contract:` commit and C4 must ignore unknown columns (it selects by name).
- Known gap: the plan does not schedule the `data-check-*.md` spec file's content because it depends on the real data; A1's human step writes it.
