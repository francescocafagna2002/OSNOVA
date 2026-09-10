# tests/test_weather.py
import gzip
from datetime import datetime
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from osnova.cli import app
from osnova.config import Config
from osnova.io.store import WEATHER, Store, assert_schema
from osnova.io.weather import (
    find_weather_files,
    group_files_by_plz,
    load_weather,
    normalize_weather,
    normalize_weather_all,
    write_weather,
)

N_HOURS = 24 * (365 + 366)  # 2023 + 2024


def test_find_and_group_synth_files(settings, truth: dict):
    files = find_weather_files(settings.weather_dir)
    plzs = truth["spec"]["plzs"]
    assert len(files) == len(plzs) * 24  # one gz per PLZ and month; sidecars and coordinates ignored
    assert all(f.name.endswith(".csv.gz") for f in files)
    groups = group_files_by_plz(files)
    assert sorted(groups) == sorted(plzs) and all(len(v) == 24 for v in groups.values())


def test_normalize_synth_plz(settings, cfg: Config, truth: dict):
    groups = group_files_by_plz(find_weather_files(settings.weather_dir))
    plz = sorted(groups)[0]
    df = normalize_weather_all(groups[plz], cfg)[plz]
    assert_schema(df, WEATHER, "weather")
    assert df["plz"].unique().to_list() == [plz]
    assert df["ts"].dtype == pl.Datetime("ms")
    # local naive: the second 02:00 of each fall-back day is dropped, so two hours fewer than UTC
    assert df.height == N_HOURS - 2
    assert df["ts"].is_sorted() and df["ts"].n_unique() == df.height
    # the download runs Jan 1 00:00 .. Dec 31 23:00 UTC, i.e. 01:00 CET .. next Jan 1 00:00 CET
    assert str(df["ts"].min()) == "2023-01-01 01:00:00" and str(df["ts"].max()) == "2025-01-01 00:00:00"
    sunny = df.group_by(pl.col("ts").dt.date()).agg(pl.col("is_sunny_day").first())["is_sunny_day"].mean()
    assert 0.2 < sunny < 0.3
    row = df.row(0, named=True)
    assert abs(row["hdd15"] - max(0.0, 15 - row["temperature_2m"])) < 1e-5
    # radiation is a daytime thing in local time: peak hour must be around local noon
    peak = (
        df.group_by(pl.col("ts").dt.hour())
        .agg(pl.col("shortwave_radiation").mean())
        .sort("shortwave_radiation")
    )
    assert peak["ts"][-1] in (11, 12, 13)


def _write_utc_file(path: Path, plz: str, start: datetime, hours: int, rad: list[float]) -> None:
    ts = pl.datetime_range(start, start + pl.duration(hours=hours - 1), "1h", eager=True)
    df = pl.DataFrame(
        {
            "PLZ": [plz] * hours,
            "timestamp_utc": ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "temperature_2m": [float(i) for i in range(hours)],
            "cloud_cover": [0.0] * hours,
            "shortwave_radiation": rad,
            "direct_radiation": [0.0] * hours,
            "diffuse_radiation": [0.0] * hours,
            "sunshine_duration": [0.0] * hours,
            "relative_humidity_2m": [50.0] * hours,
            "precipitation": [0.0] * hours,
            "snowfall": [0.0] * hours,
            "wind_speed_10m": [1.0] * hours,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(df.write_csv())


def test_utc_to_local_and_end_labelled_shift(tmp_path: Path, cfg: Config):
    # 2024-06-30 22:00 UTC .. 2024-07-01 03:00 UTC = 00:00 .. 05:00 local (CEST, UTC+2)
    p = tmp_path / "weather_part_1" / "hourly" / "5000" / "2024-06.csv.gz"
    _write_utc_file(p, "5000", datetime(2024, 6, 30, 22), 6, rad=[0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    df = normalize_weather(p, cfg)
    assert str(df["ts"][0]) == "2024-07-01 00:00:00" and str(df["ts"][-1]) == "2024-07-01 05:00:00"
    assert df["temperature_2m"].to_list() == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]  # instantaneous: unchanged
    # previous-hour mean labelled at interval end -> moved to interval start; last row keeps its own value
    assert df["shortwave_radiation"].to_list() == [10.0, 20.0, 30.0, 40.0, 50.0, 50.0]


def test_dst_days_have_unique_local_hours(tmp_path: Path, cfg: Config):
    plz_dir = tmp_path / "weather_part_1" / "hourly" / "5000"
    # spring forward: 2024-03-31 00:00 UTC .. 03:00 UTC = 01:00 CET, 03:00 CEST, 04:00, 05:00 local
    _write_utc_file(plz_dir / "2024-03.csv.gz", "5000", datetime(2024, 3, 31, 0), 4, rad=[0.0] * 4)
    # fall back: 2024-10-26 23:00 UTC .. 2024-10-27 02:00 UTC = 01:00 CEST, 02:00 CEST, 02:00 CET, 03:00 CET
    _write_utc_file(plz_dir / "2024-10.csv.gz", "5000", datetime(2024, 10, 26, 23), 4, rad=[0.0] * 4)
    df = normalize_weather_all(sorted(plz_dir.glob("*.csv.gz")), cfg)["5000"]
    hours = [str(t) for t in df["ts"]]
    assert hours[:4] == [
        "2024-03-31 01:00:00",
        "2024-03-31 03:00:00",
        "2024-03-31 04:00:00",
        "2024-03-31 05:00:00",
    ]
    assert hours[4:] == ["2024-10-27 01:00:00", "2024-10-27 02:00:00", "2024-10-27 03:00:00"]
    assert df["ts"].n_unique() == df.height


def test_write_load_and_cli(settings, cfg: Config, truth: dict, monkeypatch):
    store = Store(settings)
    groups = group_files_by_plz(find_weather_files(settings.weather_dir))
    plz = sorted(groups)[0]
    write_weather(store, normalize_weather_all(groups[plz], cfg))
    assert load_weather(store, plz) is not None and load_weather(store, "9999") is None
    monkeypatch.setenv("OSNOVA_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("OSNOVA_WEATHER_DIR", str(settings.weather_dir))
    monkeypatch.setenv("OSNOVA_STORE_DIR", str(settings.store_dir))
    r = CliRunner().invoke(app, ["weather"])
    assert r.exit_code == 0, r.output
    for p in truth["spec"]["plzs"]:
        got = load_weather(store, p)
        assert got is not None and got.height == N_HOURS - 2
        assert_schema(got, WEATHER, "weather")
    assert (store.root / "_manifest_weather.json").exists()
