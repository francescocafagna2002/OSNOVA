# tests/test_cli.py
from pathlib import Path

from typer.testing import CliRunner

from osnova.cli import app

runner = CliRunner()


def test_synth_command_writes_truth(tmp_path: Path):
    r = runner.invoke(
        app, ["synth", "--out", str(tmp_path), "--meters", "6", "--years", "2024", "--seed", "1"]
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "truth.json").exists()


def test_stub_exits_with_stream_hint():
    r = runner.invoke(app, ["train"])
    assert r.exit_code == 2 and "Stream D" in r.output
