# tests/test_explain.py
import math

import lightgbm as lgb
import numpy as np
import polars as pl

from osnova.models.explain import shap_top
from osnova.models.reasons import FEATURE_LABELS, reasons_for
from tests.synthetic_features import FEATURE_DATASET_COLUMNS


def test_feature_labels_cover_every_feature_column():
    keys = {c for c in FEATURE_DATASET_COLUMNS if c not in ("gp_nr", "plz") and not c.startswith("label_")}
    missing = keys - set(FEATURE_LABELS)
    assert not missing, missing
    assert FEATURE_LABELS["pv_prob"] == "Estimated PV probability"
    assert all(v and (v[0].isupper() or v[0].isdigit()) for v in FEATURE_LABELS.values())


def test_shap_top_returns_scaled_sorted_contributions():
    rng = np.random.default_rng(0)
    X = pl.DataFrame({"a": rng.normal(size=200), "b": rng.normal(size=200), "c": rng.normal(size=200)})
    y = (X["a"].to_numpy() * 3 + X["b"].to_numpy() > 0).astype(int)
    booster = lgb.train(
        {"objective": "binary", "verbosity": -1, "min_child_samples": 5},
        lgb.Dataset(X.to_numpy(), y, feature_name=["a", "b", "c"]),
        30,
    )
    out = shap_top(booster, X.head(5), k=2)
    assert len(out) == 5 and all(len(row) == 2 for row in out)
    for row in out:
        assert [abs(e["contribution"]) for e in row] == sorted(
            (abs(e["contribution"]) for e in row), reverse=True
        )
        assert all(-1 <= e["contribution"] <= 1 for e in row)
        assert all(e["feature"] in ("A", "B", "C") for e in row)
    # tanh(value / 2): a strong feature on a confident row is well away from zero
    assert max(abs(e["contribution"]) for row in out for e in row) > 0.3


def test_shap_top_uses_feature_labels():
    rng = np.random.default_rng(1)
    X = pl.DataFrame({"sessions_per_week": rng.normal(size=100), "noise": rng.normal(size=100)})
    y = (X["sessions_per_week"].to_numpy() > 0).astype(int)
    booster = lgb.train(
        {"objective": "binary", "verbosity": -1, "min_child_samples": 5},
        lgb.Dataset(X.to_numpy(), y, feature_name=X.columns),
        20,
    )
    names = {e["feature"] for row in shap_top(booster, X.head(3), k=6) for e in row}
    assert FEATURE_LABELS["sessions_per_week"] in names


def test_reasons_render_numbers_and_skip_nan():
    feats = {
        "sessions_per_week": 2.34,
        "session_median": 7.1,
        "evening_start_ratio": 0.5,
        "night_start_ratio": 0.3,
        "count_events_above_7kw": math.nan,
    }
    out = reasons_for("ev", feats, prob=0.9, events_day=pl.DataFrame({"type": ["ev_charging"]}))
    assert any("2.3" in r and "7.1" in r for r in out)
    assert any("80%" in r for r in out)
    assert not any("nan" in r.lower() for r in out)
    assert out[-1].startswith("Visible on the selected day")
    assert 2 <= len(out) <= 4


def test_reasons_unlikely_and_empty_features():
    for asset in ("pv", "battery", "heat_pump", "ev"):
        out = reasons_for(asset, {}, prob=0.1, events_day=None)
        assert len(out) >= 1, asset
        assert not any("Visible on" in r for r in out)


def test_reasons_never_state_the_asset_as_fact():
    feats = {"days_with_export_ratio": 0.62, "correlation_solar_radiation_consumption": -0.71}
    out = reasons_for("pv", feats, prob=0.95, events_day=None)
    joined = " ".join(out).lower()
    assert "62%" in joined and "-0.71" in joined
    assert "has pv" not in joined and "has a pv" not in joined


def test_reasons_use_none_as_missing():
    out = reasons_for(
        "heat_pump", {"correlation_outside_temperature_consumption": None}, prob=0.7, events_day=None
    )
    assert all("none" not in r.lower() for r in out)
