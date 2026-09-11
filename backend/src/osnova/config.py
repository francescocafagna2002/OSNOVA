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
    data_dir: Path = Path("data/synth/aew-data")  # Table 1 load-profile CSVs, any depth
    registry_dir: Path | None = None  # Tables 2-4; on Renku they live on another mount. None = data_dir
    weather_dir: Path = Path("data/synth/weather")  # holds weather_part_1/, weather_part_2/
    store_dir: Path = Path("data/synth/store")

    @property
    def out(self) -> Path:
        return self.store_dir / "osnova"

    @property
    def registry_root(self) -> Path:
        return self.registry_dir or self.data_dir


class CohortConfig(BaseModel):
    """The cohort itself is chosen by feature_pipeline (CohortConfig.extra_random_gps there).

    This seed only draws the random "others" sample of `osnova export`.
    """

    seed: int = 42


class IngestConfig(BaseModel):
    unit_factor: float = 4.0  # kWh per 15 min -> kW. Set to 1.0 if check-data says values are kW.
    import_obis: str = "1-1:1.29.0*255"
    export_obis: str = "1-1:2.29.0*255"
    n_buckets: int = 64
    csv_separator: str = ";"
    date_format: str = "%d.%m.%Y"


class WeatherConfig(BaseModel):
    """Open-Meteo ERA5 download: weather_part_N/hourly/<PLZ>/<YYYY-MM>.csv.gz, UTC hourly rows."""

    timezone: str = "Europe/Zurich"  # pipeline stores local naive interval starts
    utc_time_column: str = "timestamp_utc"  # ISO 8601 with Z
    local_time_column: str = "time"  # plain Open-Meteo export, already local naive
    # previous-hour means/totals: the row labelled 12:00 covers 11:00-12:00 -> relabel to interval start
    end_labelled_vars: tuple[str, ...] = (
        "shortwave_radiation",
        "direct_radiation",
        "diffuse_radiation",
        "sunshine_duration",
        "precipitation",
        "snowfall",
    )


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
    # PV generation windows (events/pv_windows.py)
    pv_export_min_kw: float = 0.1
    pv_dip_hours: tuple[int, int] = (9, 17)  # search window for the net-load dip, [start, end)
    pv_dip_ratio: float = 0.5  # net < ratio x night baseline counts as "dip"
    pv_dip_min_intervals: int = 8
    pv_radiation_corr_min: float = 0.5
    pv_conf_export_with_radiation: float = 0.9
    pv_conf_export: float = 0.7
    pv_conf_dip: float = 0.5
    # Heat-pump heating (events/hp_heating.py)
    hp_excess_kw: float = 0.8
    hp_min_transitions: int = 3
    hp_transition_window: int = 12  # intervals (3 h) in which >= hp_min_transitions switches count as cycling
    hp_morning_block: tuple[int, int] = (4, 10)  # a sustained run inside these hours is the morning block
    hp_morning_min_intervals: int = 8
    hp_night_baseline_quantile: float = 0.1  # fallback when the meter has no summer nights
    hp_conf_no_temperature: float = 0.5
    hp_conf_range: tuple[float, float] = (0.3, 0.9)
    # Battery cycles (events/battery_cycles.py)
    battery_near_zero_kw: float = 0.1
    battery_min_intervals: int = 4
    battery_radiation_min_wm2: float = 50.0  # charging only counts while the sun is up
    battery_evening: tuple[int, int] = (17, 23)
    battery_conf_one: float = 0.6  # charging or discharging block found
    battery_conf_both: float = 0.8  # both found on the same day
    # High-consumption fallback (events/high_load.py)
    high_load_quantile: float = 0.95
    high_load_min_intervals: int = 4
    high_load_confidence: float = 0.5
    showcase_min_confidence: float = 0.6


class LabelConfig(BaseModel):
    unlabeled_weight: float = 0.5
    registry_negative_weight: float = 1.0


class Config(BaseModel):
    cohort: CohortConfig = CohortConfig()
    ingest: IngestConfig = IngestConfig()
    weather: WeatherConfig = WeatherConfig()
    features: FeatureConfig = FeatureConfig()
    events: EventConfig = EventConfig()
    labels: LabelConfig = LabelConfig()


def load_config(path: Path | None = None) -> Config:
    """Defaults, optionally overridden by a JSON file with the same nesting."""
    if path is None:
        return Config()
    return Config.model_validate(json.loads(Path(path).read_text()))
