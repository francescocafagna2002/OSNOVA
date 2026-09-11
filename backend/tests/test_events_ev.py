# tests/test_events_ev.py
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from osnova.config import EventConfig
from osnova.events.ev_sessions import SESSION_SCHEMA, detect_ev_sessions, merge_runs, runs
from osnova.synth.loader import load_synth_meter
from tests.helpers import pick


def test_runs_and_merge():
    mask = np.array([0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 1], dtype=bool)
    assert runs(mask) == [(1, 3), (5, 6), (9, 11)]
    assert merge_runs(runs(mask), max_gap=2) == [(1, 6), (9, 11)]


def test_detects_injected_sessions(synth_dir, truth):
    mid = pick(truth, ev=True)
    lg = load_synth_meter(synth_dir, mid, 2024).sort("ts")
    out = detect_ev_sessions(lg["ts"].to_numpy(), lg["import_kw"].to_numpy(), EventConfig())
    assert out.schema == SESSION_SCHEMA
    expected = [
        datetime.fromisoformat(s["start"])
        for s in truth["ev_sessions"][str(mid)]
        if datetime.fromisoformat(s["start"]).year == 2024
    ]
    found = out["start"].to_list()
    hits = sum(any(abs(f - e) <= timedelta(minutes=30) for f in found) for e in expected)
    assert hits / len(expected) > 0.7
    assert abs(out["plateau_kw"].median() - truth["meters"][str(mid)]["ev_plateau_kw"]) < 0.6
    assert (out["confidence"] >= 0.5).mean() > 0.7


def test_plain_meter_has_few_sessions(synth_dir, truth):
    lg = load_synth_meter(synth_dir, pick(truth, ev=False, heat_pump=False), 2024).sort("ts")
    out = detect_ev_sessions(lg["ts"].to_numpy(), lg["import_kw"].to_numpy(), EventConfig())
    assert out.height < 10


def test_constant_series_yields_empty():
    ts = pl.datetime_range(datetime(2024, 1, 1), datetime(2024, 1, 3), "15m", eager=True).to_numpy()
    out = detect_ev_sessions(ts, np.full(len(ts), 0.4, dtype=np.float32), EventConfig())
    assert out.height == 0
