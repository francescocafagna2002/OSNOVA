# tests/test_events_contract.py
"""Team decision 2026-09-11: events and showcase are keyed by building (gp_nr), not meter."""

import polars as pl

from osnova.io.store import EVENTS, FEATURE_KEYS, SHOWCASE


def test_events_and_showcase_are_keyed_by_gp_nr():
    assert EVENTS["gp_nr"] == FEATURE_KEYS["gp_nr"] == pl.Int64 and "meter_id" not in EVENTS
    assert SHOWCASE["gp_nr"] == pl.Int64 and "meter_id" not in SHOWCASE
    assert list(EVENTS.keys())[0] == "gp_nr" and list(SHOWCASE.keys())[0] == "gp_nr"
