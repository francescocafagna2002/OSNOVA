# src/osnova/events/ev_sessions.py
"""EV charging session detector. Shared by the EV features (Stream B) and the event export (Stream C)."""

from __future__ import annotations

import numpy as np
import polars as pl

from osnova.config import EventConfig

SESSION_SCHEMA = pl.Schema(
    {
        "start": pl.Datetime("ms"),
        "end": pl.Datetime("ms"),
        "plateau_kw": pl.Float32,
        "energy_kwh": pl.Float32,
        "duration_h": pl.Float32,
        "n_intervals": pl.Int32,
        "confidence": pl.Float32,
    }
)

INTERVAL_MIN = 15


def empty_sessions() -> pl.DataFrame:
    return pl.DataFrame(schema=SESSION_SCHEMA)


def rolling_median(x: np.ndarray, window: int) -> np.ndarray:
    """Centred rolling median; the edges use the available samples."""
    return pl.Series(x).rolling_median(window_size=window, center=True, min_samples=1).to_numpy()


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Contiguous True runs as (start, end-exclusive) index pairs."""
    m = np.concatenate([[0], mask.astype(np.int8), [0]])
    d = np.diff(m)
    return list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist(), strict=True))


def merge_runs(rs: list[tuple[int, int]], max_gap: int) -> list[tuple[int, int]]:
    """Join runs separated by at most `max_gap` False samples."""
    out: list[tuple[int, int]] = []
    for s, e in rs:
        if out and s - out[-1][1] <= max_gap:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


def detect_ev_sessions(ts: np.ndarray, import_kw: np.ndarray, cfg: EventConfig) -> pl.DataFrame:
    """ts: datetime64 sorted, import_kw: same length. Returns SESSION_SCHEMA rows.

    Baseline = centred rolling median over `ev_baseline_window` intervals; a session is a run of
    residual >= `ev_residual_kw` lasting >= `ev_min_intervals` whose plateau is flat (CV <= max).
    """
    x = np.nan_to_num(np.asarray(import_kw, dtype=np.float64))
    ts = np.asarray(ts).astype("datetime64[ms]")
    if len(x) < cfg.ev_min_intervals:
        return empty_sessions()
    resid = x - rolling_median(x, cfg.ev_baseline_window)
    starts: list[int] = []
    ends: list[int] = []
    plateaus: list[float] = []
    energies: list[float] = []
    confs: list[float] = []
    for s, e in merge_runs(runs(resid >= cfg.ev_residual_kw), cfg.ev_gap_merge):
        if e - s < cfg.ev_min_intervals:
            continue
        seg = resid[s:e]
        plateau = float(np.median(seg))
        cv = float(seg.std() / plateau) if plateau > 0 else 9.0
        if cv > cfg.ev_plateau_cv_max:
            continue
        dist = min(abs(plateau - p) / p for p in cfg.ev_known_plateaus_kw)
        conf = 0.5 * (1 - cv / cfg.ev_plateau_cv_max) + 0.5 * (1 - min(dist, 1.0))
        starts.append(s)
        ends.append(e)
        plateaus.append(plateau)
        energies.append(float(seg.sum() / 4))
        confs.append(float(np.clip(conf, 0, 1)))
    if not starts:
        return empty_sessions()
    s_idx, e_idx = np.array(starts), np.array(ends)
    return pl.DataFrame(
        {
            "start": ts[s_idx],
            "end": ts[e_idx - 1] + np.timedelta64(INTERVAL_MIN, "m"),
            "plateau_kw": plateaus,
            "energy_kwh": energies,
            "duration_h": (e_idx - s_idx) / 4,
            "n_intervals": e_idx - s_idx,
            "confidence": confs,
        }
    ).cast(dict(SESSION_SCHEMA))
