"""Hourly Open-Meteo weather, normalised to one long frame keyed by (PLZ, ts).

Also derives, from the **hourly** frame only (never from a 15-minute frame
with values replicated across the four quarters of an hour — see the module
note in ``features.py``):

  * ``is_sunny_day`` / ``is_cloudy_day`` per (PLZ, date): top/bottom
    ``sunny_cloudy_percentile`` of that PLZ-*month*'s daily shortwave-radiation
    sum, so "sunny" is judged relative to the month and does not just relearn
    summer-vs-winter seasonality.

Real layout on Renku: one or more "part" directories, each containing
`hourly/<PLZ>/YYYY-MM.csv.gz` — one gzipped file per PLZ per month, PLZ being
the directory name, not the file name. ``load_weather`` reads PLZ from each
file's parent directory first (this layout), falling back to an embedded
``PLZ`` column or a PLZ found in the filename itself for any other layout it
encounters — see ``_infer_plz``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import polars as pl

from feature_pipeline.config import PathsConfig, ThresholdsConfig
from feature_pipeline.csv_utils import find_column, read_csv_flexible

logger = logging.getLogger(__name__)

HOURLY_VALUE_COLUMNS = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "snowfall",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
)


@dataclass
class WeatherData:
    # plz (str), ts (datetime, hourly, local naive) + HOURLY_VALUE_COLUMNS.
    hourly: pl.DataFrame
    # plz (str), date, is_sunny_day (bool), is_cloudy_day (bool).
    daily_sun_class: pl.DataFrame
    plz_with_weather: set[str]


def _plz_from_filename(path_name: str, regex: str) -> str | None:
    match = re.search(regex, path_name)
    return match.group(1) if match else None


_PLZ_DIR_RE = re.compile(r"^\d{4,5}$")


def _plz_from_parent_dir(path) -> str | None:
    """The real layout is `.../hourly/<PLZ>/YYYY-MM.csv.gz` — PLZ is a directory

    name, not part of the filename. Only trust this when the parent directory
    name looks like a Swiss postcode, so an unrelated folder structure falls
    through to the filename/embedded-column strategies instead.
    """
    name = path.parent.name
    return name if _PLZ_DIR_RE.match(name) else None


def load_weather(paths: PathsConfig, cfg: ThresholdsConfig) -> WeatherData:
    search_roots = paths.weather_search_roots
    files: list = []
    for root in search_roots:
        if root.exists():
            files.extend(root.glob(paths.weather_glob))
    files = sorted(set(files))
    if not files:
        logger.warning(
            "No weather files found under %s (glob %r). All weather-based "
            "features will be null.",
            search_roots,
            paths.weather_glob,
        )
        empty_hourly = pl.DataFrame(
            schema={"plz": pl.Utf8, "ts": pl.Datetime, **{c: pl.Float64 for c in HOURLY_VALUE_COLUMNS}}
        )
        empty_daily = pl.DataFrame(
            schema={"plz": pl.Utf8, "_date": pl.Date, "is_sunny_day": pl.Boolean, "is_cloudy_day": pl.Boolean}
        )
        return WeatherData(empty_hourly, empty_daily, set())

    frames: list[pl.DataFrame] = []
    for path in files:
        try:
            raw = read_csv_flexible(path)
        except Exception:
            logger.exception("Skipping unreadable weather file %s", path)
            continue

        plz_col = find_column(raw.columns, "PLZ", "plz", "postcode")
        time_col = find_column(
            raw.columns, "time", "Time", "datetime", "date", "valid_time", "timestamp", "ts"
        )
        if time_col is None:
            logger.warning(
                "Weather file %s has no recognised time column, skipping. Actual columns: %r",
                path,
                raw.columns,
            )
            continue

        # Priority: the real layout's PLZ-named parent directory, then an
        # embedded PLZ column, then a PLZ found in the filename itself.
        plz = _plz_from_parent_dir(path)
        if plz is None and plz_col is not None:
            values = raw.get_column(plz_col).drop_nulls().cast(pl.Utf8).unique().to_list()
            if len(values) == 1:
                plz = values[0]
            elif len(values) > 1:
                # A file with a per-row PLZ column covering several PLZs: keep
                # the column instead of collapsing to one value.
                plz = None
        if plz is None and plz_col is None:
            plz = _plz_from_filename(path.name, paths.weather_plz_regex)

        select_exprs = [pl.col(time_col).alias("_time_raw")]
        if plz_col is not None and plz is None:
            select_exprs.append(pl.col(plz_col).cast(pl.Utf8).alias("plz"))
        present_value_cols = []
        for value_col in HOURLY_VALUE_COLUMNS:
            src = find_column(raw.columns, value_col)
            if src is not None:
                select_exprs.append(pl.col(src).cast(pl.Float64).alias(value_col))
                present_value_cols.append(value_col)
            else:
                select_exprs.append(pl.lit(None, dtype=pl.Float64).alias(value_col))

        frame = raw.select(select_exprs)
        if "plz" not in frame.columns:
            if plz is None:
                logger.warning(
                    "Could not determine PLZ for weather file %s (no filename match, "
                    "no PLZ column); skipping.",
                    path,
                )
                continue
            frame = frame.with_columns(pl.lit(plz).alias("plz"))

        frame = frame.with_columns(
            pl.col("_time_raw")
            .str.to_datetime(strict=False, ambiguous="earliest")
            .alias("ts")
        ).drop("_time_raw")
        frames.append(frame.select("plz", "ts", *HOURLY_VALUE_COLUMNS))

    if not frames:
        raise ValueError(f"No usable weather files under {search_roots}")

    hourly = pl.concat(frames, how="vertical_relaxed").drop_nulls(subset=["ts"])

    # Daily aggregate computed ONLY from the hourly frame (24 real values per
    # day), never from a 15-minute frame where each hourly value is repeated
    # four times — that would not change a *sum* here since we aggregate
    # before any join to consumption, but the rule is kept in one place so a
    # future edit cannot introduce quadruple-counting by joining first.
    daily = (
        hourly.with_columns(
            pl.col("ts").dt.date().alias("_date"),
            pl.col("ts").dt.month().alias("_month"),
        )
        .group_by("plz", "_date", "_month")
        .agg(pl.col("shortwave_radiation").sum().alias("_daily_sw"))
    )

    monthly_bounds = daily.group_by("plz", "_month").agg(
        pl.col("_daily_sw").quantile(1 - cfg.sunny_cloudy_percentile).alias("_p_hi"),
        pl.col("_daily_sw").quantile(cfg.sunny_cloudy_percentile).alias("_p_lo"),
    )

    daily_sun_class = (
        daily.join(monthly_bounds, on=["plz", "_month"], how="left")
        .with_columns(
            (pl.col("_daily_sw") >= pl.col("_p_hi")).alias("is_sunny_day"),
            (pl.col("_daily_sw") <= pl.col("_p_lo")).alias("is_cloudy_day"),
        )
        .select("plz", "_date", "is_sunny_day", "is_cloudy_day")
    )

    return WeatherData(
        hourly=hourly,
        daily_sun_class=daily_sun_class,
        plz_with_weather=set(hourly.get_column("plz").unique().to_list()),
    )
