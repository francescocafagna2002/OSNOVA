# src/osnova/synth/weather.py
"""Plausible hourly weather for one PLZ.

Seasonal + diurnal temperature, clear-sky radiation x daily clearness.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import polars as pl

from osnova.io.store import WEATHER_VARS


def synth_weather(plz: str, years: tuple[int, ...], rng: np.random.Generator) -> pl.DataFrame:
    start, end = datetime(min(years), 1, 1), datetime(max(years), 12, 31, 23)
    ts = pl.datetime_range(start, end, "1h", eager=True).cast(pl.Datetime("ms"))
    n = ts.len()
    hour = ts.dt.hour().to_numpy().astype(float)
    doy = ts.dt.ordinal_day().to_numpy().astype(float)
    day_index = np.arange(n) // 24
    n_days = day_index.max() + 1
    clear_day = rng.beta(2.0, 2.0, size=n_days)[day_index]  # 0 = overcast, 1 = clear
    day_offset = rng.normal(0.0, 3.0, size=n_days)[day_index]
    seasonal = 0.55 + 0.45 * np.cos((doy - 172) / 365 * 2 * np.pi)
    sun = np.clip(np.cos((hour - 12) / 24 * 2 * np.pi), 0, None) ** 1.5
    shortwave = 900 * sun * seasonal * (0.25 + 0.75 * clear_day)
    direct = shortwave * clear_day * 0.8
    temperature = (
        10
        - 9 * np.cos((doy - 20) / 365 * 2 * np.pi)
        + 4 * np.sin((hour - 9) / 24 * 2 * np.pi)
        + day_offset
        + rng.normal(0, 0.5, n)
    )
    precipitation = np.where(clear_day < 0.4, rng.exponential(0.3, n), 0.0)
    cols = {
        "temperature_2m": temperature,
        "relative_humidity_2m": 55 + 30 * (1 - clear_day) + rng.normal(0, 3, n),
        "cloud_cover": 100 * (1 - clear_day),
        "shortwave_radiation": shortwave,
        "direct_radiation": direct,
        "diffuse_radiation": shortwave - direct,
        "sunshine_duration": np.where(direct > 120, 3600.0, 0.0),
        "precipitation": precipitation,
        "snowfall": np.where(temperature < 0, precipitation, 0.0),
        "wind_speed_10m": rng.gamma(2.0, 1.5, n),
    }
    assert tuple(cols) == WEATHER_VARS
    return pl.DataFrame({"plz": [plz] * n, "ts": ts, **{k: v.astype(np.float32) for k, v in cols.items()}})
