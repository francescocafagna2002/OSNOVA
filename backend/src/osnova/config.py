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
    "ev_charging",
    "pv_generation",
    "heat_pump_heating",
    "battery_cycle",
    "high_consumption",
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
