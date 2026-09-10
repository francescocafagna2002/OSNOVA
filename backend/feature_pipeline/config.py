"""Central configuration for the feature-extraction pipeline.

Every threshold, time window and path lives here so nothing is hard-coded
inside a feature function. Change a default here (or override via CLI flags
in ``scripts/build_feature_dataset.py``) rather than editing feature code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class TimeWindow:
    """A daypart as [start_hour, end_hour) in local time. ``wraps`` = crosses midnight."""

    name: str
    start_hour: int
    end_hour: int

    @property
    def wraps(self) -> bool:
        return self.start_hour > self.end_hour


@dataclass(frozen=True)
class PathsConfig:
    """Real input locations. Override with CLI flags / env vars — never hard-code

    a machine-specific absolute path in feature code.
    """

    # Root that contains the yearly consumption folders (2023/, 2024/, ...).
    # Matches the brief: "aew-data/test-blob/input_data/". The mapping/labels
    # files below default to *the same* root because the brief describes them
    # as siblings of the year folders there.
    raw_consumption_dir: Path = Path("aew-data/test-blob/input_data")
    # Glob (relative to raw_consumption_dir) for the wide consumption CSVs.
    # Matched by filename ("LG_AIM2Hackerdays_kWh_....csv", per the brief)
    # rather than "**/*.csv" so it does not also pick up the mapping/labels
    # CSVs that live under the same root.
    raw_consumption_glob: str = "**/LG_AIM2Hackerdays_kWh_*.csv"

    mp_mapping_file: Path = Path("aew-data/test-blob/input_data/mpid_zähler_mapping.csv")
    zaehler_gp_file: Path = Path("aew-data/test-blob/input_data/Zähler-GP.csv")
    labels_file: Path = Path("aew-data/test-blob/input_data/HackDays2026 - GIGI.csv")

    # Real layout (confirmed on Renku): one or more "part" directories, each
    # `<part>/hourly/<PLZ>/YYYY-MM.csv.gz` (+ a sibling `.json` metadata file
    # per month, currently unused). Point this at the directory that contains
    # the part folders, e.g. the parent of `weather_part_1/`, `weather_part_2/`.
    # PLZ is read from each file's immediate parent directory name; the glob
    # matches both plain `.csv` and gzipped `.csv.gz`.
    weather_dir: Path = Path("aew-data/test-blob/input_data/weather")
    # If the "part" directories have no shared parent (or you'd rather list
    # them explicitly), set this instead — it takes priority over
    # ``weather_dir`` when non-empty. Each entry is searched independently.
    weather_dirs: tuple[Path, ...] = ()
    weather_glob: str = "**/*.csv*"
    weather_plz_regex: str = r"(\d{4,5})"

    @property
    def weather_search_roots(self) -> tuple[Path, ...]:
        return self.weather_dirs if self.weather_dirs else (self.weather_dir,)

    # Where intermediate and final outputs are written.
    output_dir: Path = Path("data/feature_output")
    intermediate_dir: Path = Path("data/feature_output/intermediate")

    @property
    def feature_dataset_path(self) -> Path:
        return self.output_dir / "feature_dataset.parquet"

    @property
    def sessions_debug_path(self) -> Path:
        return self.output_dir / "ev_candidate_sessions.parquet"

    @property
    def audit_path(self) -> Path:
        return self.output_dir / "audit_report.json"

    @property
    def manifest_path(self) -> Path:
        return self.intermediate_dir / "ingest_manifest.json"

    @property
    def by_file_dir(self) -> Path:
        return self.intermediate_dir / "by_file"


@dataclass(frozen=True)
class TimeWindows:
    """Dayparts and seasons. Boundaries are half-open [start, end)."""

    night: TimeWindow = field(default_factory=lambda: TimeWindow("night", 22, 6))
    morning: TimeWindow = field(default_factory=lambda: TimeWindow("morning", 6, 10))
    midday: TimeWindow = field(default_factory=lambda: TimeWindow("midday", 10, 16))
    evening: TimeWindow = field(default_factory=lambda: TimeWindow("evening", 16, 22))

    summer_months: tuple[int, ...] = (6, 7, 8)
    winter_months: tuple[int, ...] = (12, 1, 2)

    def all(self) -> tuple[TimeWindow, ...]:
        return (self.night, self.morning, self.midday, self.evening)


@dataclass(frozen=True)
class TemperatureBin:
    name: str
    low: float | None  # None = -inf
    high: float | None  # None = +inf


@dataclass(frozen=True)
class ThresholdsConfig:
    """All numeric thresholds. Every one is referenced by name from feature code."""

    interval_minutes: int = 15
    timezone: str = "Europe/Zurich"

    # --- shared "near zero" / "meaningful signal" epsilons ---
    near_zero_epsilon_kw: float = 0.2
    near_zero_min_intervals: int = 2  # 2 * 15 min = 30 min
    export_epsilon_kw: float = 0.2  # for negative_consumption_ratio / export-day detection

    # --- solar radiation ---
    solar_radiation_min_wm2: float = 100.0  # "meaningful" radiation for ratio/correlation scope
    sunny_cloudy_percentile: float = 0.25  # top/bottom 25% of days per (plz, month)

    # --- EV high-load thresholds & event/session detection ---
    ev_event_thresholds_kw: tuple[float, ...] = (3.0, 5.0, 7.0, 11.0)
    ev_min_event_intervals: int = 2  # 30 min, same rule for all four thresholds

    ev_session_threshold_kw: float = 3.0
    ev_min_session_minutes: int = 30

    @property
    def ev_min_session_intervals(self) -> int:
        return max(1, self.ev_min_session_minutes // self.interval_minutes)

    # --- correlations ---
    corr_min_observations: int = 30

    # --- heat pump temperature bins (mutually exclusive) ---
    temperature_bins: tuple[TemperatureBin, ...] = (
        TemperatureBin("below_minus5", None, -5.0),
        TemperatureBin("minus5_to_0", -5.0, 0.0),
        TemperatureBin("0_to_5", 0.0, 5.0),
        TemperatureBin("5_to_10", 5.0, 10.0),
        TemperatureBin("10_to_15", 10.0, 15.0),
        TemperatureBin("above_15", 15.0, None),
    )
    min_temp_bin_observations: int = 20

    # --- MP -> building aggregation strategy, centralised (see mapping.py) ---
    # "sum": building_power_kw(t) = sum of power_kw of all MPs of that GP-Nr at t.
    multi_mp_strategy: str = "sum"
    # Strategy for >1 raw row at the exact same (MP ID, timestamp) — e.g. a
    # second OBIS-Code row. OBIS-Code itself is not used to split import/export
    # per the brief, so duplicates are collapsed the same way multi-MP is.
    duplicate_mp_timestamp_strategy: str = "sum"


@dataclass(frozen=True)
class PipelineConfig:
    paths: PathsConfig = field(default_factory=PathsConfig)
    windows: TimeWindows = field(default_factory=TimeWindows)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)


DEFAULT_CONFIG = PipelineConfig()
