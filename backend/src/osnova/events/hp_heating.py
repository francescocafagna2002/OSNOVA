# src/osnova/events/hp_heating.py
"""Heat-pump heating: winter days where import exceeds the summer-night baseline, cycling or morning block."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from osnova.config import EventConfig, FeatureConfig
from osnova.events.ev_sessions import runs
from osnova.events.pv_windows import WINDOW_SCHEMA, empty_windows
from osnova.features.base import add_calendar

INTERVAL = timedelta(minutes=15)
# Card C6 literals; they belong in EventConfig once config.py is open to this stream.
TRANSITION_WINDOW = 12  # intervals (3 h) in which >= hp_min_transitions on/off switches count as cycling
MORNING_BLOCK = (4, 10)  # a sustained run inside these hours counts as the morning heating block
MORNING_MIN_INTERVALS = 8
CONF_NO_TEMPERATURE = 0.5
CONF_RANGE = (0.3, 0.9)
NIGHT_P10 = 0.1


def _baseline_kw(df: pl.DataFrame, fcfg: FeatureConfig) -> float:
    lo, hi = fcfg.night
    night = df.filter((pl.col("hour") >= lo) & (pl.col("hour") < hi) & pl.col("import_kw").is_not_null())
    summer = night.filter(pl.col("season") == "summer")["import_kw"]
    if summer.len():
        return float(summer.median())
    if night.height:
        return float(night["import_kw"].quantile(NIGHT_P10))
    return 0.0


def _day_event(day: pl.DataFrame, baseline: float, cfg: EventConfig) -> dict | None:
    imp = day["import_kw"].fill_null(0.0).to_numpy().astype(np.float64)
    hour = day["hour"].to_numpy()
    excess = imp - baseline
    on = excess >= cfg.hp_excess_kw
    if not on.any():
        return None
    switches = np.abs(np.diff(on.astype(np.int8)))
    cycling = False
    if len(switches) >= TRANSITION_WINDOW:
        kernel = np.ones(TRANSITION_WINDOW, dtype=np.int32)
        cycling = np.convolve(switches, kernel, mode="valid").max() >= cfg.hp_min_transitions
    else:
        cycling = switches.sum() >= cfg.hp_min_transitions
    morning = any(
        e - s >= MORNING_MIN_INTERVALS and hour[s] >= MORNING_BLOCK[0] and hour[e - 1] < MORNING_BLOCK[1]
        for s, e in runs(on)
    )
    if not (cycling or morning):
        return None
    idx = np.flatnonzero(on)
    ts = day["ts"]
    return {
        "start": ts[int(idx[0])],
        "end": ts[int(idx[-1])] + INTERVAL,
        "peak_kw": float(imp[on].max()),
        "energy_kwh": float(np.clip(excess[on], 0, None).sum() / 4),
    }


def detect_hp_heating(df: pl.DataFrame, cfg: EventConfig, fcfg: FeatureConfig | None = None) -> pl.DataFrame:
    """df: ts, import_kw, temperature_2m (nullable), optionally season/hour. One event per winter day."""
    if df.height == 0:
        return empty_windows()
    fcfg = fcfg or FeatureConfig()
    if "season" not in df.columns or "hour" not in df.columns:
        df = add_calendar(df.sort("ts"), fcfg)
    else:
        df = df.sort("ts")
    if "temperature_2m" not in df.columns:
        df = df.with_columns(temperature_2m=pl.lit(None, pl.Float32))
    baseline = _baseline_kw(df, fcfg)
    winter = df.filter(pl.col("season") == "winter").with_columns(day=pl.col("ts").dt.date())
    if winter.height == 0:
        return empty_windows()
    corr = winter.select(
        pl.corr(pl.col("temperature_2m").cast(pl.Float64), pl.col("import_kw").cast(pl.Float64))
    )[0, 0]
    confidence = (
        CONF_NO_TEMPERATURE
        if corr is None or np.isnan(corr) or winter["temperature_2m"].null_count() == winter.height
        else float(np.clip(-corr, *CONF_RANGE))
    )
    rows = []
    for _, day in winter.partition_by("day", as_dict=True, maintain_order=True).items():
        ev = _day_event(day, baseline, cfg)
        if ev is not None:
            rows.append({**ev, "confidence": confidence})
    if not rows:
        return empty_windows()
    return pl.DataFrame(rows).select(list(WINDOW_SCHEMA.keys())).cast(dict(WINDOW_SCHEMA)).sort("start")
