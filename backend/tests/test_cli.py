# tests/test_cli.py
import json
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from osnova.cli import app
from osnova.io.store import LABELS, PREDICTIONS, assert_schema
from tests.synthetic_features import synthetic_table

runner = CliRunner()


def test_synth_command_writes_truth(tmp_path: Path):
    r = runner.invoke(
        app, ["synth", "--out", str(tmp_path), "--meters", "6", "--years", "2024", "--seed", "1"]
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "truth.json").exists()


def test_events_without_building_series_fails_loudly(tmp_path: Path):
    r = runner.invoke(app, ["events"], env={"OSNOVA_STORE_DIR": str(tmp_path / "store")})
    assert r.exit_code == 1 and "feature_output/intermediate/by_file" in r.output


def test_export_without_predictions_fails_loudly(tmp_path: Path):
    r = runner.invoke(app, ["export"], env={"OSNOVA_STORE_DIR": str(tmp_path / "store")})
    assert r.exit_code == 1 and "predictions.parquet" in r.output


@pytest.mark.parametrize("stage", ["registry", "ingest", "features"])
def test_retired_stages_point_to_feature_pipeline(stage: str):
    r = runner.invoke(app, [stage])
    assert r.exit_code == 2
    assert "scripts/build_feature_dataset.py" in r.output and "gp_nr" in r.output


def test_train_end_to_end_on_synthetic_feature_table(tmp_path: Path):
    feats, dates, _ = synthetic_table(150, seed=3)
    out = tmp_path / "store" / "osnova"
    (out / "feature_output").mkdir(parents=True)
    feats.write_parquet(out / "feature_output" / "feature_dataset.parquet")
    dates.write_parquet(out / "feature_output" / "gigi_dates.parquet")
    r = runner.invoke(app, ["train"], env={"OSNOVA_STORE_DIR": str(tmp_path / "store")})
    assert r.exit_code == 0, r.output
    preds = pl.read_parquet(out / "predictions.parquet")
    assert_schema(preds, PREDICTIONS, "predictions")
    assert preds.height == feats.height
    assert_schema(pl.read_parquet(out / "labels.parquet"), LABELS, "labels")
    for name in ("pv.txt", "battery_calibration.joblib", "metrics.json", "feature_importance.parquet"):
        assert (out / "models" / name).exists(), name
    manifest = json.loads((out / "_manifest_train.json").read_text())
    assert manifest["n_buildings"] == feats.height and manifest["stage"] == "train"
    assert "registry" in r.output and "roc_auc" in r.output and "battery" in r.output


def test_train_without_dates_file_warns_and_runs(tmp_path: Path):
    feats, _, _ = synthetic_table(60, seed=4)
    out = tmp_path / "store" / "osnova"
    (out / "feature_output").mkdir(parents=True)
    feats.write_parquet(out / "feature_output" / "feature_dataset.parquet")
    r = runner.invoke(app, ["train"], env={"OSNOVA_STORE_DIR": str(tmp_path / "store")})
    assert r.exit_code == 0, r.output
    assert "no commissioning dates" in r.output


def test_train_fails_loudly_without_feature_table(tmp_path: Path):
    r = runner.invoke(app, ["train"], env={"OSNOVA_STORE_DIR": str(tmp_path / "store")})
    assert r.exit_code == 1 and "feature_dataset.parquet" in r.output
