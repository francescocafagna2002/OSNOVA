# tests/test_labels.py
from datetime import date

import polars as pl

from osnova.config import LabelConfig
from osnova.io.store import LABELS, assert_schema
from osnova.labels.build import build_labels


def _features() -> pl.DataFrame:
    # gp 1: PV yes (no date), EV explicit no, others unknown
    # gp 2: PV yes commissioned late, battery yes commissioned early, EV/HP unknown
    # gp 3: not in GIGI at all
    # gp 4: heat pump yes, commissioned exactly on the cutoff day
    return pl.DataFrame(
        {
            "gp_nr": [1, 2, 3, 4],
            "plz": ["5000"] * 4,
            "num_mp_ids": [1, 2, 1, 1],
            "n_valid_days": [400, 400, 400, 400],
            "label_pv": [1, 1, None, None],
            "label_ev": [0, None, None, None],
            "label_heatpump": [None, None, None, 1],
            "label_battery": [None, 1, None, None],
            "sessions_per_week": [0.1, 0.2, 0.3, 0.4],
        }
    ).cast({"gp_nr": pl.Int64, "label_pv": pl.Int8, "label_ev": pl.Int8, "label_heatpump": pl.Int8})


def _dates() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "gp_nr": [1, 2, 4],
            "commissioned_pv": [None, date(2026, 1, 15), None],
            "commissioned_ev": [None, None, None],
            "commissioned_heatpump": [None, None, date(2025, 7, 1)],
            "commissioned_battery": [None, date(2024, 3, 1), None],
        },
        schema={
            "gp_nr": pl.Int64,
            "commissioned_pv": pl.Date,
            "commissioned_ev": pl.Date,
            "commissioned_heatpump": pl.Date,
            "commissioned_battery": pl.Date,
        },
    )


def _get(out: pl.DataFrame, gp: int, asset: str) -> dict | None:
    r = out.filter((pl.col("gp_nr") == gp) & (pl.col("asset") == asset))
    return r.row(0, named=True) if r.height else None


def test_label_rules_per_building():
    out = build_labels(_features(), _dates(), LabelConfig())
    assert_schema(out, LABELS, "labels")
    # flag 1, no date -> positive from the registry
    assert _get(out, 1, "pv") == {"gp_nr": 1, "asset": "pv", "label": 1, "weight": 1.0, "source": "registry"}
    # flag 0 -> negative from the registry
    assert _get(out, 1, "ev")["label"] == 0 and _get(out, 1, "ev")["source"] == "registry"
    # flag null while other flags known -> unknown, no row
    assert _get(out, 1, "heat_pump") is None and _get(out, 1, "battery") is None
    # flag 1 but commissioned after the visibility cutoff -> no row
    assert _get(out, 2, "pv") is None
    # flag 1 commissioned before the cutoff -> positive
    assert _get(out, 2, "battery")["label"] == 1
    # commissioned exactly on the cutoff day counts as visible
    assert _get(out, 4, "heat_pump")["label"] == 1
    # not in GIGI -> weak negative for every asset
    for asset in ("pv", "battery", "heat_pump", "ev"):
        row = _get(out, 3, asset)
        assert row["label"] == 0 and row["weight"] == 0.5 and row["source"] == "unlabeled"
    assert out.height == 2 + 1 + 4 + 1


def test_unlabeled_weight_comes_from_config():
    out = build_labels(_features(), _dates(), LabelConfig(unlabeled_weight=0.25))
    assert _get(out, 3, "ev")["weight"] == 0.25


def test_missing_dates_frame_means_no_commissioning_dates():
    out = build_labels(_features(), None, LabelConfig())
    assert _get(out, 2, "pv")["label"] == 1
