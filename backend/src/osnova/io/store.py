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

REGISTRY = pl.Schema(
    {
        "meter_id": I64,
        "zaehlpunkt": STR,
        "gp_nr": I64,
        "anlage": STR,
        "plz": STR,
        "ort": STR,
        "kanton": STR,
        "meters_per_gp": I32,
        "has_pv": BOOL,
        "has_battery": BOOL,
        "has_hp": BOOL,
        "has_ev": BOOL,
        "has_hp_boiler": BOOL,
        "pv_kwp": F32,
        "commissioned_on": pl.Date,
    }
)
LASTGANG = pl.Schema(
    {
        "meter_id": I64,
        "ts": DT,
        "plz": STR,
        "import_kw": F32,
        "export_kw": F32,
        "net_kw": F32,
        "quality": STR,
    }
)
WEATHER_VARS: tuple[str, ...] = (
    "temperature_2m",
    "relative_humidity_2m",
    "cloud_cover",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
    "precipitation",
    "snowfall",
    "wind_speed_10m",
)
WEATHER = pl.Schema(
    {
        "plz": STR,
        "ts": DT,
        **{v: F32 for v in WEATHER_VARS},
        "is_sunny_day": BOOL,
        "is_cloudy_day": BOOL,
        "hdd15": F32,
    }
)
# Feature table = feature_pipeline's feature_dataset.parquet: one row per building (gp_nr, whole
# history, team decision 2026-09-11). These are the key columns; feature columns are FINAL_COLUMNS in
# feature_pipeline/pipeline.py. PREDICTIONS / EVENTS / SHOWCASE move to gp_nr in Sessions 2 and 3.
FEATURE_KEYS = pl.Schema({"gp_nr": I64, "plz": STR, "n_valid_days": I32})
LABELS = pl.Schema({"gp_nr": I64, "asset": STR, "label": pl.Int8, "weight": F32, "source": STR})
# Events and showcase are keyed by building (gp_nr as in FEATURE_KEYS), decision 2026-09-11.
EVENTS = pl.Schema(
    {
        "gp_nr": I64,
        "type": STR,
        "start": DT,
        "end": DT,
        "confidence": F32,
        "peak_kw": F32,
        "energy_kwh": F32,
    }
)
SHOWCASE = pl.Schema({"gp_nr": I64, "showcase_date": pl.Date, "n_event_types": I32})
PREDICTIONS = pl.Schema(
    {
        "gp_nr": I64,  # one row per building, whole history
        "prob_pv": F32,  # calibrated
        "prob_battery": F32,
        "prob_heat_pump": F32,
        "prob_ev": F32,
        "raw_pv": F32,  # uncalibrated LightGBM score
        "raw_battery": F32,
        "raw_heat_pump": F32,
        "raw_ev": F32,
        "shap_pv": STR,  # JSON list of {"feature", "contribution"}, top 6 by |contribution|
        "shap_battery": STR,
        "shap_heat_pump": STR,
        "shap_ev": STR,
    }
)


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

    def registry_path(self) -> Path:
        return self.root / "registry.parquet"

    def cohort_path(self) -> Path:
        return self.root / "cohort.parquet"

    def lastgang_dir(self) -> Path:
        return self.root / "lastgang"

    def bucket_path(self, bucket: int) -> Path:
        return self.lastgang_dir() / f"bucket={bucket:02d}" / "part.parquet"

    def weather_dir(self) -> Path:
        return self.root / "weather"

    def weather_path(self, plz: str) -> Path:
        return self.weather_dir() / f"plz={plz}.parquet"

    def feature_output_dir(self) -> Path:
        """feature_pipeline output (scripts/build_feature_dataset.py --output-dir)."""
        return self.root / "feature_output"

    def features_path(self) -> Path:
        return self.feature_output_dir() / "feature_dataset.parquet"

    def features_skipped_path(self) -> Path:
        return self.root / "features_skipped.parquet"

    def labels_path(self) -> Path:
        return self.root / "labels.parquet"

    def events_path(self) -> Path:
        return self.root / "events.parquet"

    def showcase_path(self) -> Path:
        return self.root / "showcase.parquet"

    def predictions_path(self) -> Path:
        return self.root / "predictions.parquet"

    def models_dir(self) -> Path:
        return self.root / "models"

    def export_dir(self) -> Path:
        return self.root / "export"

    def buildings_json(self) -> Path:
        return self.export_dir() / "buildings.json"

    def featured_json(self) -> Path:
        return self.export_dir() / "featured.json"

    def data_check_json(self) -> Path:
        return self.root / "data_check.json"

    def logs_dir(self) -> Path:
        return self.root / "logs"

    def write_manifest(self, stage: str, **info: Any) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"_manifest_{stage}.json"
        payload = {
            "stage": stage,
            "git_sha": _git_sha(),
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            **{k: (str(v) if isinstance(v, Path) else v) for k, v in info.items()},
        }
        path.write_text(json.dumps(payload, indent=2, default=str))
        return path


def scan_lastgang(store: Store) -> pl.LazyFrame:
    return pl.scan_parquet(store.lastgang_dir() / "bucket=*" / "part.parquet")
