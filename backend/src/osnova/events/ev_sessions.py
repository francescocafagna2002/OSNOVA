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


def empty_sessions() -> pl.DataFrame:
    return pl.DataFrame(schema=SESSION_SCHEMA)


def detect_ev_sessions(ts: np.ndarray, import_kw: np.ndarray, cfg: EventConfig) -> pl.DataFrame:
    """ts: datetime64[ms] sorted, import_kw: float32 same length. Returns SESSION_SCHEMA rows."""
    raise NotImplementedError("Stream C, card C1")
