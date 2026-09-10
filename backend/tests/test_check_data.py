# tests/test_check_data.py
import gzip
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
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
    # weather: synth writes the ERA5 layout (24 monthly gz per PLZ, UTC), continuous, no gaps
    assert report["weather"]["n_files"] == len(truth["spec"]["plzs"]) * 24
    assert report["weather"]["n_plz"] == len(truth["spec"]["plzs"])
    assert report["weather"]["time_column"] == "timestamp_utc"
    assert report["weather"]["time_zone_hint"] == "utc"
    assert "temperature_2m" in report["weather"]["columns"]
    assert report["weather"]["time_min"] == "2023-01-01 00:00:00"  # UTC, as downloaded
    assert report["weather"]["time_max"] == "2024-12-31 23:00:00"
    assert report["weather"]["hour_gaps"] == 0 and report["weather"]["duplicate_hours"] == 0
    assert all(p["success_marker"] for p in report["weather"]["parts"].values())
    assert set(report["weather"]["plz_in_table1"]) <= set(report["weather"]["plz_with_weather"])


RENKU_WEATHER_COLS = [
    "PLZ",
    "timestamp_utc",
    "temperature_2m",
    "cloud_cover",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
    "relative_humidity_2m",
    "precipitation",
    "snowfall",
    "wind_speed_10m",
]


def _write_renku_weather(root: Path, parts: dict[str, list[str]], months: list[str], drop_hour: bool = False):
    """The ERA5 download layout: weather_part_N/hourly/<plz>/<YYYY-MM>.csv.gz, comma-separated, UTC."""
    for part, plzs in parts.items():
        d = root / part
        (d / "hourly").mkdir(parents=True)
        (d / "metadata.json").write_text("{}")
        (d / "plz_coordinates.csv").write_text("PLZ,lat,lon\n5073,47.4,8.0\n")
        (d / "swisstopo_postcodes_4326.csv.zip").write_bytes(b"PK\x03\x04junk")
        for plz in plzs:
            for month in months:
                y, m = (int(x) for x in month.split("-"))
                start = datetime(y, m, 1)
                end = datetime(y + (m == 12), m % 12 + 1, 1) - timedelta(hours=1)
                ts = pl.datetime_range(start, end, "1h", eager=True)
                if drop_hour:
                    ts = ts.filter(ts.dt.hour() != 12) if month == months[0] else ts
                n = ts.len()
                df = pl.DataFrame(
                    {
                        "PLZ": [plz] * n,
                        "timestamp_utc": ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        **{c: [1.0] * n for c in RENKU_WEATHER_COLS[2:]},
                    }
                )
                (d / "hourly" / plz).mkdir(exist_ok=True)
                with gzip.open(d / "hourly" / plz / f"{month}.csv.gz", "wt", encoding="utf-8") as fh:
                    fh.write(df.write_csv())
                (d / "hourly" / plz / f"{month}.json").write_text("{}")
    (root / "weather_part_1" / "_SUCCESS.json").write_text("{}")


def test_check_data_weather_renku_layout(synth_dir: Path, tmp_path: Path):
    wdir = tmp_path / "store"
    _write_renku_weather(
        wdir, {"weather_part_1": ["5073", "5000"], "weather_part_2": ["5400"]}, ["2023-01", "2023-02"]
    )
    w = run_check(synth_dir / "aew-data", wdir, Config(), max_files=1)["weather"]
    assert w["n_files"] == 6  # 3 PLZ x 2 months; coordinates csv, zip and json sidecars ignored
    assert w["n_plz"] == 3 and w["files_per_plz_min"] == 2 and w["files_per_plz_max"] == 2
    assert w["columns"] == RENKU_WEATHER_COLS
    assert w["time_column"] == "timestamp_utc" and w["time_zone_hint"] == "utc"
    assert w["time_min"] == "2023-01-01 00:00:00" and w["time_max"] == "2023-02-28 23:00:00"
    assert w["hour_gaps"] == 0 and w["duplicate_hours"] == 0 and w["continuity_files"] == 2
    assert w["parts"]["weather_part_1"] == {"success_marker": True, "metadata": True, "n_plz_dirs": 2}
    assert w["parts"]["weather_part_2"]["success_marker"] is False
    assert w["plz_with_weather"] == ["5000", "5073", "5400"]
    assert "5105" in w["plz_missing"] and "5000" not in w["plz_missing"]


def test_check_data_weather_detects_hour_gap(synth_dir: Path, tmp_path: Path):
    wdir = tmp_path / "store"
    _write_renku_weather(wdir, {"weather_part_1": ["5073"]}, ["2023-01", "2023-02"], drop_hour=True)
    w = run_check(synth_dir / "aew-data", wdir, Config(), max_files=1)["weather"]
    assert w["hour_gaps"] == 31  # one missing 12:00 per January day


def test_check_data_real_mount_layout(synth_dir: Path, tmp_path: Path, truth: dict):
    """Renku: consumption under <year>/<German month>/LG_…_<export stamp>.csv, registry on another mount."""
    cons = tmp_path / "cleaned_data"
    copies = {
        "2023/01/lastgang_2023_01.csv": "2023/Januar 2023/LG_AIM2Hackerdays_kWh_20260825_131305.csv",
        "2023/03/lastgang_2023_03.csv": "2023/März 2023/LG_AIM2Hackerdays_kWh_20260827_084034.csv",
    }
    for src, dst in copies.items():
        (cons / dst).parent.mkdir(parents=True)
        shutil.copy(synth_dir / "aew-data" / "lastgang" / src, cons / dst)
    reg = tmp_path / "input_data"
    shutil.copytree(synth_dir / "aew-data" / "registry", reg)
    report = run_check(cons, synth_dir / "weather", Config(), max_files=1, registry_dir=reg)
    assert report["registry_dir"] == str(reg)
    # year from the folder, not from the 2026 export stamp in the file name
    assert report["files"]["per_year"] == {"2023": sorted(copies.values())}
    # only January is sampled; March is found through the folder name and scanned for DST
    assert len(report["files"]["sampled"]) == 1
    assert report["dst_null_cells"]["days_checked"] == ["26.03.2023"]
    assert report["dst_null_cells"]["files_checked"] == ["LG_AIM2Hackerdays_kWh_20260827_084034.csv"]
    labeled = sum(t["labeled"] for t in truth["meters"].values())
    assert report["registry"]["n_gp"] == labeled and report["registry"]["n_meters_joined"] == labeled
    keys = report["registry"]["keys"]
    assert keys["table2_gp"]["all_digits"] is True and keys["table4_gp"]["with_decimal_suffix"] == 0
    assert report["registry"]["joined_with_normalized_keys"]["n_meters_joined"] == labeled


def test_check_data_join_diagnostics_detect_key_format_mismatch(synth_dir: Path, tmp_path: Path):
    reg = tmp_path / "registry"
    reg.mkdir()
    (reg / "buildings.csv").write_text("GP-Nr;PLZ;PV\n500001;5000;ja\n500002;5000;ja\n")
    (reg / "meters.csv").write_text("MP ID;Zählpunktbezeichnung\n1;CH1\n2;CH2\n3;CH3\n")
    # Excel-style float and a leading zero on the GP side: raw join fails, normalized join works
    (reg / "installations.csv").write_text(
        "Zählpunktbezeichnung;GPartner;Anlage\nCH1;500001.0;A\nCH2;0500001;B\nCH3;500002;C\n"
    )
    r = run_check(synth_dir / "aew-data", synth_dir / "weather", Config(), max_files=1, registry_dir=reg)[
        "registry"
    ]
    assert r["n_gp"] == 2 and r["n_gp_table4"] == 3 and r["n_meters_with_gp_in_table4"] == 3
    assert r["n_meters_joined"] == 1 and r["n_gp_table4_in_table2"] == 1
    assert r["keys"]["table4_gp"] == {
        "n": 3,
        "n_unique": 3,
        "n_null": 0,
        "len_min": 6,
        "len_max": 8,
        "all_digits": False,
        "with_leading_zero": 1,
        "with_decimal_suffix": 1,
        "with_inner_whitespace": 0,
        "with_non_ascii": 0,
    }
    norm = r["joined_with_normalized_keys"]
    assert norm["n_meters_joined"] == 3 and norm["n_gp_with_meter"] == 2
    assert norm["meters_per_gp_hist"] == {"1": 1, "2": 1}


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
