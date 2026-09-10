# tests/test_synth.py
import json
from pathlib import Path

import polars as pl

EXPECTED_HEADER = (
    "MP ID;OBIS-Code;Datum;PLZ;"
    + ";".join(f"{(i // 4) % 24:02d}:{(i % 4) * 15:02d}" for i in range(1, 97))
    + ";"
)


def test_lastgang_files_have_real_layout(synth_dir: Path):
    files = sorted((synth_dir / "aew-data" / "lastgang").rglob("*.csv"))
    assert len(files) == 24  # 2 years x 12 months
    first_line = files[0].read_text(encoding="utf-8").splitlines()[0]
    assert first_line == EXPECTED_HEADER  # "...;23:45;00:00;"
    df = pl.read_csv(files[6], separator=";", truncate_ragged_lines=True)  # July of year 1
    assert df["OBIS-Code"].unique().sort().to_list() == ["1-1:1.29.0*255", "1-1:2.29.0*255"]
    assert df["Datum"].str.contains(r"^\d{2}\.\d{2}\.\d{4}$").all()


def test_pv_meter_exports_at_noon_in_july(synth_dir: Path, truth: dict):
    pv_ids = [int(m) for m, t in truth["meters"].items() if t["pv"] and t["commissioned_on"] is None]
    assert pv_ids, "synth must contain PV meters commissioned before the data window"
    df = pl.read_csv(
        synth_dir / "aew-data" / "lastgang" / "2024" / "07" / "lastgang_2024_07.csv",
        separator=";",
        truncate_ragged_lines=True,
    )
    exp = df.filter((pl.col("MP ID") == pv_ids[0]) & (pl.col("OBIS-Code") == "1-1:2.29.0*255"))
    assert exp["12:00"].mean() > 0.05  # kWh per 15 min


def test_daily_import_energy_is_household_sized(synth_dir: Path):
    df = pl.read_csv(
        synth_dir / "aew-data" / "lastgang" / "2024" / "01" / "lastgang_2024_01.csv",
        separator=";",
        truncate_ragged_lines=True,
    )
    imp = df.filter(pl.col("OBIS-Code") == "1-1:1.29.0*255")
    daily = imp.select(pl.sum_horizontal(pl.exclude(["MP ID", "OBIS-Code", "Datum", "PLZ"]).cast(pl.Float64)))
    assert 3 < daily.to_series().median() < 60


def test_registry_and_weather_files(synth_dir: Path, truth: dict):
    t2 = pl.read_excel(synth_dir / "aew-data" / "registry" / "Table2_Buildings.xlsx")
    assert {"GP-Nr", "PLZ", "PV", "Ladestation für EV", "InBetrieb-Datum"} <= set(t2.columns)
    t3 = pl.read_csv(synth_dir / "aew-data" / "registry" / "Table3_MeterPoints.csv", separator=";")
    t4 = pl.read_csv(synth_dir / "aew-data" / "registry" / "Table4_Installations.csv", separator=";")
    assert t3.columns == ["MP ID", "Zählpunktbezeichnung"] and t4.columns == [
        "Zählpunktbezeichnung",
        "GPartner",
        "Anlage",
    ]
    labeled = [m for m, t in truth["meters"].items() if t["labeled"]]
    assert t2.height == len(labeled)
    # weather: the ERA5 download layout, UTC hours, one gz per PLZ and month, split in two parts
    parts = sorted(p.name for p in (synth_dir / "weather").iterdir() if p.is_dir())
    assert parts == ["weather_part_1", "weather_part_2"]
    for part in parts:
        assert {"metadata.json", "plz_coordinates.csv", "_SUCCESS.json"} <= {
            p.name for p in (synth_dir / "weather" / part).iterdir()
        }
    months = sorted((synth_dir / "weather").rglob("hourly/5000/*.csv.gz"))
    assert len(months) == 24 and months[0].name == "2023-01.csv.gz"
    w = pl.concat([pl.read_csv(m) for m in months])
    assert w.columns[:2] == ["PLZ", "timestamp_utc"]
    assert {"temperature_2m", "shortwave_radiation", "sunshine_duration"} <= set(w.columns)
    assert w.height == 24 * (366 + 365)  # 2023 + 2024 (leap), continuous in UTC
    assert w["timestamp_utc"].str.ends_with("Z").all()
    assert (
        w["timestamp_utc"][0] == "2023-01-01T00:00:00Z" and w["timestamp_utc"][-1] == "2024-12-31T23:00:00Z"
    )


def test_truth_covers_every_asset(truth: dict):
    for asset in ("pv", "battery", "heat_pump", "ev"):
        assert any(t[asset] for t in truth["meters"].values()), asset
    assert (json.dumps(truth)) and truth["spec"]["meters"] == 24


def test_loader_roundtrip(synth_dir: Path, truth: dict):
    from osnova.io.store import LASTGANG, assert_schema
    from osnova.synth.loader import load_synth_meter, load_synth_weather

    mid = next(int(m) for m, t in truth["meters"].items() if t["pv"])
    lg = load_synth_meter(synth_dir, mid, 2024)
    assert_schema(lg, LASTGANG, "lastgang")
    assert lg.height == 366 * 96 and lg["export_kw"].max() > 0.5
    w = load_synth_weather(synth_dir, lg["plz"][0])
    # local naive hours: the duplicated 02:00 of each fall-back day is dropped
    assert {"is_sunny_day", "hdd15"} <= set(w.columns) and w.height == 24 * 366 + 24 * 365 - 2
