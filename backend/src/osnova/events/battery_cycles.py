# src/osnova/events/battery_cycles.py
"""Battery cycles: on sunny export days, net ~ 0 while radiation rises (charging) and in the evening."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from osnova.config import EventConfig
from osnova.events.ev_sessions import runs
from osnova.events.pv_windows import WINDOW_SCHEMA, empty_windows

INTERVAL = timedelta(minutes=15)


def _runs_to_rows(day: pl.DataFrame, mask: np.ndarray, net: np.ndarray, min_intervals: int) -> list[dict]:
    ts = day["ts"]
    out = []
    for s, e in runs(mask):
        if e - s < min_intervals:
            continue
        seg = np.abs(net[s:e])
        out.append(
            {
                "start": ts[s],
                "end": ts[e - 1] + INTERVAL,
                "peak_kw": float(seg.max()),
                "energy_kwh": float(seg.sum() / 4),
            }
        )
    return out


def _day_cycles(day: pl.DataFrame, cfg: EventConfig) -> list[dict]:
    net = day["net_kw"].fill_null(np.inf).to_numpy().astype(np.float64)
    rad = day["shortwave_radiation"].fill_null(0.0).to_numpy().astype(np.float64)
    hour = day["ts"].dt.hour().to_numpy()
    near_zero = np.abs(net) < cfg.battery_near_zero_kw
    peak = int(rad.argmax())
    idx = np.arange(len(net))
    lo, hi = cfg.battery_evening
    charging = _runs_to_rows(
        day, near_zero & (idx < peak) & (rad > cfg.battery_radiation_min_wm2), net, cfg.battery_min_intervals
    )
    discharging = _runs_to_rows(day, near_zero & (hour >= lo) & (hour < hi), net, cfg.battery_min_intervals)
    conf = cfg.battery_conf_both if charging and discharging else cfg.battery_conf_one
    return [{**r, "confidence": conf} for r in charging + discharging]


def detect_battery_cycles(df: pl.DataFrame, cfg: EventConfig) -> pl.DataFrame:
    """df: ts, net_kw, export_kw, shortwave_radiation (nullable), is_sunny_day (nullable). Events per run."""
    if df.height == 0 or "is_sunny_day" not in df.columns:
        return empty_windows()
    if "shortwave_radiation" not in df.columns:
        df = df.with_columns(shortwave_radiation=pl.lit(None, pl.Float32))
    days = (
        df.sort("ts")
        .with_columns(day=pl.col("ts").dt.date())
        .with_columns(day_export=pl.col("export_kw").max().over("day"))
        .filter(pl.col("is_sunny_day").fill_null(False) & (pl.col("day_export") > cfg.pv_export_min_kw))
    )
    rows: list[dict] = []
    for _, day in days.partition_by("day", as_dict=True, maintain_order=True).items():
        rows.extend(_day_cycles(day, cfg))
    if not rows:
        return empty_windows()
    return pl.DataFrame(rows).select(list(WINDOW_SCHEMA.keys())).cast(dict(WINDOW_SCHEMA)).sort("start")
