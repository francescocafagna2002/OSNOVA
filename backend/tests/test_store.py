# tests/test_store.py
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from osnova.config import OsnovaSettings
from osnova.io.store import FEATURE_KEYS, LASTGANG, SchemaError, Store, assert_schema
from osnova.io.weather import upsample_15min


def test_store_paths(tmp_path: Path):
    st = Store(OsnovaSettings(store_dir=tmp_path))
    assert st.weather_path("5000") == tmp_path / "osnova" / "weather" / "plz=5000.parquet"
    assert st.events_path() == tmp_path / "osnova" / "events.parquet"
    assert st.buildings_json() == tmp_path / "osnova" / "export" / "buildings.json"
    assert st.features_path() == tmp_path / "osnova" / "feature_output" / "feature_dataset.parquet"


def test_feature_keys_are_building_grain():
    """Team decision 2026-09-11: one row per building, no meter_id, no year."""
    assert list(FEATURE_KEYS) == ["gp_nr", "plz", "n_valid_days"]
    assert FEATURE_KEYS["gp_nr"] == pl.Int64 and FEATURE_KEYS["n_valid_days"] == pl.Int32
    row = pl.DataFrame(
        {"gp_nr": [123456], "plz": ["5000"], "n_valid_days": [700], "total_export_kwh": [12.5]}
    ).cast({"gp_nr": pl.Int64, "n_valid_days": pl.Int32})
    assert_schema(row, FEATURE_KEYS, "features", subset=True)
    with pytest.raises(SchemaError):
        old_grain = row.drop("gp_nr").with_columns(meter_id=pl.lit(1))
        assert_schema(old_grain, FEATURE_KEYS, "features", subset=True)


def test_assert_schema_rejects_wrong_dtype():
    df = pl.DataFrame(
        {
            "meter_id": [1],
            "ts": [datetime(2024, 1, 1)],
            "plz": ["5000"],
            "import_kw": [1.0],
            "export_kw": [0.0],
            "net_kw": [1.0],
            "quality": ["ok"],
        }
    )
    with pytest.raises(SchemaError):
        assert_schema(df, LASTGANG, "lastgang")  # floats are f64, schema wants f32
    assert_schema(df.cast(dict(LASTGANG)), LASTGANG, "lastgang")


def test_manifest_written(tmp_path: Path):
    st = Store(OsnovaSettings(store_dir=tmp_path))
    p = st.write_manifest("ingest", rows=10)
    assert p.exists() and '"rows": 10' in p.read_text()


def test_upsample_15min_interpolates_temperature():
    hourly = pl.DataFrame(
        {
            "plz": ["5000", "5000"],
            "ts": [datetime(2024, 1, 1, 0), datetime(2024, 1, 1, 1)],
            "temperature_2m": [0.0, 4.0],
            "shortwave_radiation": [100.0, 200.0],
        }
    )
    out = upsample_15min(hourly)
    assert out.height == 5  # 00:00, 00:15, 00:30, 00:45, 01:00
    assert out["temperature_2m"].to_list() == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert out["shortwave_radiation"].to_list() == [100.0, 100.0, 100.0, 100.0, 200.0]
