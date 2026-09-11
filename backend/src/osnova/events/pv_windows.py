# src/osnova/events/pv_windows.py
"""PV generation windows: one row per day with export, or a midday net-load dip on a sunny day."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from osnova.config import EventConfig
from osnova.events.ev_sessions import runs

WINDOW_SCHEMA = pl.Schema(
    {
        "start": pl.Datetime("ms"),
        "end": pl.Datetime("ms"),
        "confidence": pl.Float32,
        "peak_kw": pl.Float32,
        "energy_kwh": pl.Float32,
    }
)
INTERVAL = timedelta(minutes=15)


def empty_windows() -> pl.DataFrame:
    return pl.DataFrame(schema=WINDOW_SCHEMA)


def _export_days(df: pl.DataFrame, cfg: EventConfig) -> pl.DataFrame:
    thr = cfg.pv_export_min_kw
    has_rad = "shortwave_radiation" in df.columns
    above = pl.col("export_kw") > thr
    corr = (
        pl.corr(pl.col("export_kw"), pl.col("shortwave_radiation").fill_null(0.0))
        if has_rad
        else pl.lit(None, pl.Float64)
    )
    rad_ok = pl.col("shortwave_radiation").is_not_null().any() if has_rad else pl.lit(False)
    days = (
        df.group_by(pl.col("ts").dt.date().alias("day"))
        .agg(
            start=pl.col("ts").filter(above).min(),
            end=pl.col("ts").filter(above).max() + INTERVAL,
            peak_kw=pl.col("export_kw").max(),
            energy_kwh=pl.col("export_kw").filter(above).sum() / 4,
            corr=corr,
            rad_ok=rad_ok,
        )
        .filter(pl.col("peak_kw") > thr)
        .with_columns(
            confidence=pl.when(pl.col("rad_ok") & (pl.col("corr") > cfg.pv_radiation_corr_min))
            .then(cfg.pv_conf_export_with_radiation)
            .otherwise(cfg.pv_conf_export)
        )
    )
    return days.select(["day", "start", "end", "confidence", "peak_kw", "energy_kwh"])


def _dip_window(day: pl.DataFrame, night_baseline_kw: float, cfg: EventConfig) -> dict | None:
    hours = day["ts"].dt.hour().to_numpy()
    lo, hi = cfg.pv_dip_hours
    in_window = (hours >= lo) & (hours < hi)
    net = day["net_kw"].fill_null(np.inf).to_numpy().astype(np.float64)
    mask = in_window & (net < cfg.pv_dip_ratio * night_baseline_kw)
    best = max(runs(mask), key=lambda r: r[1] - r[0], default=None)
    if best is None or best[1] - best[0] < cfg.pv_dip_min_intervals:
        return None
    s, e = best
    seg = net[s:e]
    ts = day["ts"]
    return {
        "start": ts[s],
        "end": ts[e - 1] + INTERVAL,
        "confidence": cfg.pv_conf_dip,
        "peak_kw": float(-seg.min()),
        "energy_kwh": float(np.clip(night_baseline_kw - seg, 0, None).sum() / 4),
    }


def detect_pv_windows(df: pl.DataFrame, night_baseline_kw: float, cfg: EventConfig) -> pl.DataFrame:
    """df: ts, export_kw, net_kw, shortwave_radiation (nullable), is_sunny_day (nullable), any span of days.

    Export days: first..last interval with export > pv_export_min_kw. Otherwise on sunny days the
    longest pv_dip_hours run of net < pv_dip_ratio x night baseline (>= pv_dip_min_intervals).
    Days with neither give no row.
    """
    if df.height == 0:
        return empty_windows()
    df = df.sort("ts")
    export_days = _export_days(df, cfg)
    rows: list[dict] = []
    if "is_sunny_day" in df.columns:
        sunny = df.with_columns(day=pl.col("ts").dt.date()).filter(
            pl.col("is_sunny_day").fill_null(False) & ~pl.col("day").is_in(export_days["day"].implode())
        )
        for _, day in sunny.partition_by("day", as_dict=True, maintain_order=True).items():
            win = _dip_window(day, night_baseline_kw, cfg)
            if win is not None:
                rows.append(win)
    dips = pl.DataFrame(rows, schema=WINDOW_SCHEMA) if rows else empty_windows()
    out = pl.concat([export_days.drop("day").cast(dict(WINDOW_SCHEMA)), dips])
    return out.sort("start")
