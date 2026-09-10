"""Time-column helpers shared by ingest and feature computation.

Keeps the "which columns are quarter-hour values" and "which daypart is this
hour in" logic in one place instead of duplicated across modules.
"""

from __future__ import annotations

import re

import polars as pl

from feature_pipeline.config import ThresholdsConfig, TimeWindow, TimeWindows

QUARTER_COLUMN_RE = re.compile(r"^([01]\d|2[0-3]):(00|15|30|45)$")


def quarter_hour_columns(columns: list[str]) -> list[str]:
    """Return the subset of ``columns`` that look like 'HH:MM' quarter-hour labels.

    Detected by regex rather than a hard-coded list of 96 names so real files
    with a slightly different header order still work. Order among the
    returned names does not matter: each is converted to an explicit
    ``(hour, minute)`` offset before being combined with ``Datum``, so the
    physical column order in the CSV (…, 23:45, 00:00) never matters either —
    "00:00" is always the *first* quarter hour of that same ``Datum``, per the
    brief.
    """
    return [c for c in columns if QUARTER_COLUMN_RE.match(c.strip())]


def quarter_label_to_minutes(label: str) -> int:
    """'00:00' -> 0, '00:15' -> 15, ..., '23:45' -> 1425 minutes after midnight."""
    hour, minute = label.strip().split(":")
    return int(hour) * 60 + int(minute)


def daypart_expr(hour_col: str, window: TimeWindow) -> pl.Expr:
    h = pl.col(hour_col)
    if window.wraps:
        return (h >= window.start_hour) | (h < window.end_hour)
    return (h >= window.start_hour) & (h < window.end_hour)


def add_calendar_columns(lf: pl.LazyFrame, ts_col: str = "ts") -> pl.LazyFrame:
    """Attach hour/month/date + one boolean column per daypart/season.

    Column names: ``is_night``, ``is_morning``, ``is_midday``, ``is_evening``,
    ``is_summer``, ``is_winter``.
    """
    windows = TimeWindows()
    lf = lf.with_columns(
        pl.col(ts_col).dt.hour().alias("_hour"),
        pl.col(ts_col).dt.month().alias("_month"),
        pl.col(ts_col).dt.date().alias("_date"),
        pl.col(ts_col).dt.truncate("1h").alias("_ts_hour"),
    )
    daypart_exprs = [
        daypart_expr("_hour", w).alias(f"is_{w.name}") for w in windows.all()
    ]
    lf = lf.with_columns(daypart_exprs)
    lf = lf.with_columns(
        pl.col("_month").is_in(list(windows.summer_months)).alias("is_summer"),
        pl.col("_month").is_in(list(windows.winter_months)).alias("is_winter"),
    )
    return lf


def temperature_bin_expr(temp_col: str, cfg: ThresholdsConfig) -> pl.Expr:
    """A categorical expression naming which mutually-exclusive temperature bin

    each row falls into (or ``null`` when temperature is missing).
    """
    expr = pl.lit(None, dtype=pl.Utf8)
    for tb in cfg.temperature_bins:
        cond = pl.lit(True)
        if tb.low is not None:
            cond = cond & (pl.col(temp_col) >= tb.low)
        if tb.high is not None:
            cond = cond & (pl.col(temp_col) < tb.high)
        expr = pl.when(cond).then(pl.lit(tb.name)).otherwise(expr)
    return expr
