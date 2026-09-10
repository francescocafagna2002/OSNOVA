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
    exprs = [pl.col(c).interpolate() if c in INTERPOLATED else pl.col(c).forward_fill() for c in value_cols]
    return out.with_columns(exprs).with_columns(plz=pl.lit(plz)).select(["plz", "ts", *value_cols])


__all__ = ["WEATHER_VARS", "upsample_15min"]
