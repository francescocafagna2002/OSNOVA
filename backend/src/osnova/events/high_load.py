# src/osnova/events/high_load.py
"""High-consumption fallback band: per day the longest run above the day's p95 that nobody claimed."""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from osnova.config import EventConfig
from osnova.events.pv_windows import WINDOW_SCHEMA, empty_windows

INTERVAL = timedelta(minutes=15)
P95 = 0.95
CONFIDENCE = 0.5
FULL_DAY = 96  # a run covering the whole day is a flat day, not a peak


def detect_high_load(df: pl.DataFrame, claimed: pl.DataFrame, cfg: EventConfig) -> pl.DataFrame:
    """df: ts, import_kw. claimed: start, end intervals of other detectors. One row per day at most."""
    if df.height == 0:
        return empty_windows()
    d = (
        df.select("ts", "import_kw")
        .sort("ts")
        .with_row_index("i")
        .with_columns(day=pl.col("ts").dt.date())
        .with_columns(p95=pl.col("import_kw").quantile(P95).over("day"))
        .filter(pl.col("import_kw") >= pl.col("p95"))
        .with_columns(run=(pl.col("i").diff().fill_null(2) != 1).cum_sum())
    )
    run_rows = (
        d.group_by("run")
        .agg(
            day=pl.col("day").first(),
            start=pl.col("ts").min(),
            end=pl.col("ts").max() + INTERVAL,
            n=pl.len(),
            peak_kw=pl.col("import_kw").max(),
            energy_kwh=pl.col("import_kw").sum() / 4,
        )
        .filter((pl.col("n") >= cfg.high_load_min_intervals) & (pl.col("n") < FULL_DAY))
    )
    if run_rows.height == 0:
        return empty_windows()
    if claimed.height > 0:
        c = claimed.select(
            c_start=pl.col("start").cast(pl.Datetime("ms")), c_end=pl.col("end").cast(pl.Datetime("ms"))
        )
        hits = (
            run_rows.select(
                "run", s=pl.col("start").cast(pl.Datetime("ms")), e=pl.col("end").cast(pl.Datetime("ms"))
            )
            .join_where(c, pl.col("s") < pl.col("c_end"), pl.col("e") > pl.col("c_start"))
            .select("run")
            .unique()
        )
        run_rows = run_rows.join(hits, on="run", how="anti")
    best = run_rows.sort(["day", "n", "start"], descending=[False, True, False]).unique("day", keep="first")
    return (
        best.select("start", "end", pl.lit(CONFIDENCE).alias("confidence"), "peak_kw", "energy_kwh")
        .cast(dict(WINDOW_SCHEMA))
        .sort("start")
    )
