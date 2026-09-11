# src/osnova/events/showcase.py
"""Showcase day: the day with the most distinct confident event types."""

from __future__ import annotations

from datetime import date

import polars as pl

from osnova.config import EventConfig


def pick_showcase_day(events: pl.DataFrame, cfg: EventConfig) -> tuple[date, int] | None:
    """events: type, start, confidence. Most distinct types >= min confidence, then sum, then latest."""
    if events.height == 0:
        return None
    ranked = (
        events.filter(pl.col("confidence") >= cfg.showcase_min_confidence)
        .group_by(pl.col("start").dt.date().alias("day"))
        .agg(n_types=pl.col("type").n_unique(), conf_sum=pl.col("confidence").sum())
        .sort(["n_types", "conf_sum", "day"], descending=[True, True, True])
    )
    if ranked.height == 0:
        return None
    row = ranked.row(0, named=True)
    return row["day"], int(row["n_types"])


def last_full_day(series: pl.DataFrame, intervals_per_day: int = 96) -> date | None:
    """Fallback showcase date: the last date with a full day of ok rows, else the last date at all."""
    if series.height == 0:
        return None
    ok_days = (
        series.filter(pl.col("quality") == "ok")
        .group_by(pl.col("ts").dt.date().alias("day"))
        .len()
        .filter(pl.col("len") >= intervals_per_day)
    )
    if ok_days.height:
        return ok_days["day"].max()
    return series["ts"].dt.date().max()
