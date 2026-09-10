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
    df: (
        pl.DataFrame
    )  # LASTGANG columns + CALENDAR_COLUMNS + WEATHER_VARS (+ is_sunny_day, is_cloudy_day, hdd15)


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
        pl.when((h >= cfg.night[0]) & (h < cfg.night[1]))
        .then(pl.lit("night"))
        .when((h >= cfg.morning[0]) & (h < cfg.morning[1]))
        .then(pl.lit("morning"))
        .when((h >= cfg.midday[0]) & (h < cfg.midday[1]))
        .then(pl.lit("midday"))
        .when((h >= cfg.evening[0]) & (h < cfg.evening[1]))
        .then(pl.lit("evening"))
        .otherwise(pl.lit("other"))
    )


def _season_expr(cfg: FeatureConfig) -> pl.Expr:
    m = pl.col("month")
    return (
        pl.when(m.is_in(list(cfg.summer_months)))
        .then(pl.lit("summer"))
        .when(m.is_in(list(cfg.winter_months)))
        .then(pl.lit("winter"))
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


def make_meter_year(
    lastgang: pl.DataFrame, weather_hourly: pl.DataFrame | None, cfg: FeatureConfig
) -> MeterYear:
    """Rows of one meter and one calendar year -> MeterYear with calendar and weather columns."""
    df = add_calendar(lastgang.sort("ts"), cfg)
    weather_cols = [*WEATHER_VARS, "is_sunny_day", "is_cloudy_day", "hdd15"]
    if weather_hourly is not None and weather_hourly.height > 0:
        w = upsample_15min(weather_hourly).drop("plz")
        df = df.join(w, on="ts", how="left")
    missing = [c for c in weather_cols if c not in df.columns]
    df = df.with_columns(
        [pl.lit(None, dtype=pl.Boolean if c.startswith("is_") else pl.Float32).alias(c) for c in missing]
    )
    first = df.row(0, named=True)
    return MeterYear(
        meter_id=int(first["meter_id"]), year=int(first["ts"].year), plz=str(first["plz"]), df=df
    )
