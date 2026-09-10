# tests/test_features_base.py
from datetime import datetime, timedelta

import polars as pl

from osnova.config import FeatureConfig
from osnova.features.base import MeterYear, feature_group, make_meter_year, registered_groups, run_all


def _lastgang(n_days: int = 3) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    ts = [start + timedelta(minutes=15 * i) for i in range(96 * n_days)]
    return pl.DataFrame(
        {
            "meter_id": [1] * len(ts),
            "ts": ts,
            "plz": ["5000"] * len(ts),
            "import_kw": [0.5] * len(ts),
            "export_kw": [0.0] * len(ts),
            "net_kw": [0.5] * len(ts),
            "quality": ["ok"] * len(ts),
        }
    ).cast(
        {
            "meter_id": pl.Int64,
            "ts": pl.Datetime("ms"),
            "import_kw": pl.Float32,
            "export_kw": pl.Float32,
            "net_kw": pl.Float32,
        }
    )


def _weather(n_days: int = 3) -> pl.DataFrame:
    start = datetime(2024, 1, 1)
    ts = [start + timedelta(hours=h) for h in range(24 * n_days)]
    return pl.DataFrame(
        {
            "plz": ["5000"] * len(ts),
            "ts": ts,
            "temperature_2m": [float(h % 24) for h in range(len(ts))],
            "shortwave_radiation": [0.0] * len(ts),
        }
    ).cast({"ts": pl.Datetime("ms")})


def test_make_meter_year_adds_calendar_and_weather():
    my = make_meter_year(_lastgang(), _weather(), FeatureConfig())
    assert isinstance(my, MeterYear) and my.year == 2024 and my.plz == "5000"
    row = my.df.filter(pl.col("ts") == datetime(2024, 1, 1, 7, 30)).row(0, named=True)
    assert row["hour"] == 7 and row["minute_of_day"] == 450 and row["daypart"] == "morning"
    assert row["season"] == "winter" and row["is_weekend"] is False
    assert abs(row["temperature_2m"] - 7.5) < 1e-6  # interpolated between 7 and 8
    assert my.df.height == 96 * 3


def test_make_meter_year_without_weather_has_null_weather_columns():
    my = make_meter_year(_lastgang(), None, FeatureConfig())
    assert my.df["temperature_2m"].null_count() == my.df.height


def test_feature_registry_runs_group():
    @feature_group("testgroup")
    def f(my: MeterYear, cfg: FeatureConfig) -> dict[str, float]:
        return {"mean_kw": float(my.df["net_kw"].mean())}

    my = make_meter_year(_lastgang(), None, FeatureConfig())
    out = run_all(my, FeatureConfig(), groups=["testgroup"])
    assert out == {"mean_kw": 0.5}
    assert "testgroup" in registered_groups()
