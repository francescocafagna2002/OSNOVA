# tests/test_train.py
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from sklearn.metrics import roc_auc_score

from osnova.config import Config
from osnova.io.store import LABELS, PREDICTIONS, assert_schema
from osnova.labels.build import build_labels
from osnova.models.baseline import BASE_COLUMNS, baseline_scores
from osnova.models.train import TrainResult, feature_columns, train_all
from tests.synthetic_features import ASSETS, FEATURE_DATASET_COLUMNS, synthetic_table


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> tuple[TrainResult, pl.DataFrame, dict, Path]:
    feats, dates, truth = synthetic_table()
    labels = build_labels(feats, dates, Config().labels)
    assert_schema(labels, LABELS, "labels")
    models_dir = tmp_path_factory.mktemp("store") / "models"
    result = train_all(feats, labels, Config(), models_dir)
    return result, feats, truth, models_dir


def test_feature_columns_exclude_keys_labels_and_all_null():
    feats, _, _ = synthetic_table(20)
    cols = feature_columns(feats)
    assert "sessions_per_week" in cols and "mean_consumption_T_below_minus5" in cols
    for banned in ("gp_nr", "plz", "num_mp_ids", "n_valid_days"):
        assert banned not in cols
    assert not any(c.startswith("label_") for c in cols)


def test_baseline_scores_shape_and_range():
    feats, _, truth = synthetic_table(80)
    base = baseline_scores(feats)
    assert base.columns == ["gp_nr", *BASE_COLUMNS]
    for a in ASSETS:
        assert base[f"base_{a}"].is_between(0, 1).all()
        assert roc_auc_score(truth[a], base[f"base_{a}"].to_numpy()) > 0.8, a


def test_train_all_learns_synthetic_signal(trained):
    result, feats, truth, models_dir = trained
    for a in ASSETS:
        reg = result.metrics[a]["registry"]
        assert reg["roc_auc"] > 0.9, (a, reg)
        assert reg["n"] < result.metrics[a]["all"]["n"]
        for k in ("pr_auc", "brier", "precision_at_50", "recall_at_50", "precision_at_80", "recall_at_80"):
            assert k in reg and k in result.metrics[a]["all"]
        assert "roc_auc" in result.metrics[a]["baseline"]["registry"]
        assert "comparison" in result.metrics[a]
        assert (models_dir / f"{a}.txt").exists()
        assert (models_dir / f"{a}_calibration.joblib").exists()
        # the final model scores every building, including the unlabeled ones
        assert roc_auc_score(truth[a], result.predictions[f"prob_{a}"].to_numpy()) > 0.9, a
    assert json.loads((models_dir / "metrics.json").read_text()).keys() == set(ASSETS)
    imp = pl.read_parquet(models_dir / "feature_importance.parquet")
    assert set(imp.columns) == {"asset", "feature", "gain", "split"} and set(imp["asset"]) == set(ASSETS)


def test_predictions_schema_and_grain(trained):
    result, feats, _, _ = trained
    assert_schema(result.predictions, PREDICTIONS, "predictions")
    assert result.predictions.height == feats.height
    assert result.predictions["gp_nr"].to_list() == feats["gp_nr"].to_list()


def test_calibration_is_monotone_and_does_not_hurt_brier(trained):
    result, _, _, _ = trained
    for a in ASSETS:
        reg = result.metrics[a]["registry"]
        assert reg["brier_calibrated"] <= reg["brier"] + 0.01, a
        p = result.predictions.sort(f"raw_{a}")
        assert (np.diff(p[f"prob_{a}"].to_numpy()) >= -1e-6).all(), a


def test_shap_json_is_top6_bounded_and_sorted(trained):
    result, _, _, _ = trained
    for a in ASSETS:
        entries = json.loads(result.predictions[f"shap_{a}"][0])
        assert 1 <= len(entries) <= 6
        contribs = [e["contribution"] for e in entries]
        assert all(-1 <= c <= 1 for c in contribs)
        assert [abs(c) for c in contribs] == sorted((abs(c) for c in contribs), reverse=True)
        assert all(set(e) == {"feature", "contribution"} for e in entries)


def test_battery_sees_out_of_fold_pv_probability(trained):
    result, _, _, _ = trained
    assert "pv_prob" in result.models["battery"].feature_names
    assert "pv_prob" not in result.models["pv"].feature_names
    assert "pv_prob" not in result.models["ev"].feature_names


def test_training_order_is_pv_heat_pump_ev_battery(trained):
    result, _, _, _ = trained
    assert list(result.models) == ["pv", "heat_pump", "ev", "battery"]


def test_synthetic_table_has_the_team_columns():
    feats, dates, _ = synthetic_table(10)
    assert feats.columns == FEATURE_DATASET_COLUMNS
    assert dates.columns == [
        "gp_nr",
        "commissioned_pv",
        "commissioned_battery",
        "commissioned_heatpump",
        "commissioned_ev",
    ]
