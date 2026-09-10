# tests/test_store.py
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest

from osnova.config import OsnovaSettings
from osnova.io.store import LASTGANG, SchemaError, Store, assert_schema
from osnova.io.weather import upsample_15min


def test_store_paths(tmp_path: Path):
    st = Store(OsnovaSettings(store_dir=tmp_path))
    assert st.lastgang_dir() == tmp_path / "osnova" / "lastgang"
    assert st.bucket_path(5) == tmp_path / "osnova" / "lastgang" / "bucket=05" / "part.parquet"
    assert st.buildings_json() == tmp_path / "osnova" / "export" / "buildings.json"


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
