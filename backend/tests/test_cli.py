# tests/test_cli.py
from pathlib import Path

import pytest
from typer.testing import CliRunner

from osnova.cli import app

runner = CliRunner()


def test_synth_command_writes_truth(tmp_path: Path):
    r = runner.invoke(
        app, ["synth", "--out", str(tmp_path), "--meters", "6", "--years", "2024", "--seed", "1"]
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "truth.json").exists()


def test_stub_exits_with_session_hint():
    r = runner.invoke(app, ["train"])
    assert r.exit_code == 2 and "Session 2" in r.output


@pytest.mark.parametrize("stage", ["registry", "ingest", "features"])
def test_retired_stages_point_to_feature_pipeline(stage: str):
    r = runner.invoke(app, [stage])
    assert r.exit_code == 2
    assert "scripts/build_feature_dataset.py" in r.output and "gp_nr" in r.output
