# tests/test_check_data.py
import json
from pathlib import Path

from typer.testing import CliRunner

from osnova.cli import app
from osnova.config import Config, OsnovaSettings
from osnova.io.check_data import run_check, to_markdown


def test_check_data_on_synth(synth_dir: Path, truth: dict):
    report = run_check(synth_dir / "aew-data", synth_dir / "weather", Config(), max_files=2)
    assert set(report["obis_counts"]) == {"1-1:1.29.0*255", "1-1:2.29.0*255"}
    assert report["unit_guess"] == "kwh_per_15min"
    labeled = sum(t["labeled"] for t in truth["meters"].values())
    assert report["registry"]["n_gp"] == labeled
    assert report["registry"]["n_meters_joined"] == labeled
    assert report["weather"]["plz_missing"] == []
    md = to_markdown(report)
    assert "unit_guess" in md and "1-1:2.29.0*255" in md


def test_check_data_files_dst_and_registry_details(synth_dir: Path, truth: dict):
    report = run_check(synth_dir / "aew-data", synth_dir / "weather", Config(), max_files=2)
    # 2 years x 12 monthly files, two files sampled
    assert report["files"]["count"] == 24
    assert sorted(report["files"]["per_year"]) == ["2023", "2024"]
    assert len(report["files"]["sampled"]) == 2
    # the sampled files are Jan/Feb, so the March files must be found by name for the DST check;
    # synth has no DST holes, so the cells are fully populated
    assert report["dst_null_cells"]["days_checked"] == ["26.03.2023", "31.03.2024"]
    assert report["dst_null_cells"]["files_checked"] == ["lastgang_2023_03.csv", "lastgang_2024_03.csv"]
    assert report["dst_null_cells"]["total"] == 0
    # registry: every labeled meter is its own GP in synth
    n_meters = len(truth["meters"])
    assert report["registry"]["n_meters_table3"] == n_meters
    assert report["registry"]["meters_per_gp_hist"] == {"1": report["registry"]["n_gp"]}
    assert set(report["registry"]["columns"]) == {"table2", "table3", "table4"}
    # weather: one file per PLZ, Open-Meteo columns present, no hour gaps
    assert len(report["weather"]["files"]) == len(truth["spec"]["plzs"])
    assert "temperature_2m" in report["weather"]["columns"]
    assert report["weather"]["time_min"] == "2023-01-01 00:00:00"
    assert report["weather"]["time_max"] == "2024-12-31 23:00:00"
    assert report["weather"]["hour_gaps"] == 0
    assert set(report["weather"]["plz_in_table1"]) <= set(report["weather"]["plz_with_weather"])


def test_check_data_cli_writes_json_and_prints_markdown(synth_dir: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OSNOVA_DATA_DIR", str(synth_dir / "aew-data"))
    monkeypatch.setenv("OSNOVA_WEATHER_DIR", str(synth_dir / "weather"))
    monkeypatch.setenv("OSNOVA_STORE_DIR", str(tmp_path / "store"))
    r = CliRunner().invoke(app, ["check-data", "--max-files", "1"])
    assert r.exit_code == 0, r.output
    assert "## unit_guess" in r.output
    out = OsnovaSettings().out
    report = json.loads((out / "data_check.json").read_text())
    assert report["unit_guess"] == "kwh_per_15min"
    assert (out / "_manifest_check_data.json").exists()
