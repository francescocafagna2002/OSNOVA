# src/osnova/synth/loader.py
"""Read synthetic files back as pipeline frames, so feature/detector tests do not need the ingest stage."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from osnova.io.store import LASTGANG, WEATHER_VARS
from osnova.synth.generate import EXPORT_OBIS, IMPORT_OBIS, SLOT_COLUMNS

UNIT_FACTOR = 4.0  # synth writes kWh per 15 min


def load_synth_meter(synth_dir: Path, meter_id: int, year: int) -> pl.DataFrame:
    files = sorted((synth_dir / "aew-data" / "lastgang" / str(year)).rglob("*.csv"))
    wide = pl.concat(
        [
            pl.read_csv(
                f,
                separator=";",
                truncate_ragged_lines=True,
                schema_overrides={
                    "MP ID": pl.Int64,
                    "PLZ": pl.String,
                    **{s: pl.Float32 for s in SLOT_COLUMNS},
                },
            )
            .select(["MP ID", "OBIS-Code", "Datum", "PLZ", *SLOT_COLUMNS])
            .filter(pl.col("MP ID") == meter_id)
            for f in files
        ]
    )
    idx = {s: i for i, s in enumerate(SLOT_COLUMNS)}
    long = (
        wide.unpivot(
            index=["MP ID", "OBIS-Code", "Datum", "PLZ"],
            on=SLOT_COLUMNS,
            variable_name="slot",
            value_name="v",
        )
        .with_columns(
            ts=pl.col("Datum").str.to_date("%d.%m.%Y").cast(pl.Datetime("ms"))
            + pl.duration(minutes=pl.col("slot").replace_strict(idx, return_dtype=pl.Int32) * 15)
        )
        .group_by(["MP ID", "ts", "PLZ"])
        .agg(
            import_kw=pl.col("v").filter(pl.col("OBIS-Code") == IMPORT_OBIS).first() * UNIT_FACTOR,
            export_kw=pl.col("v").filter(pl.col("OBIS-Code") == EXPORT_OBIS).first().fill_null(0.0)
            * UNIT_FACTOR,
        )
        .with_columns(net_kw=pl.col("import_kw") - pl.col("export_kw"), quality=pl.lit("ok"))
        .rename({"MP ID": "meter_id", "PLZ": "plz"})
        .select(list(LASTGANG.keys()))
        .cast(dict(LASTGANG))
        .sort("ts")
    )
    return long


def load_synth_weather(synth_dir: Path, plz: str) -> pl.DataFrame:
    df = pl.read_csv(synth_dir / "weather" / f"open-meteo_{plz}.csv", schema_overrides={"plz": pl.String})
    df = df.with_columns(
        ts=pl.col("time").str.to_datetime("%Y-%m-%dT%H:%M").cast(pl.Datetime("ms")),
        **{v: pl.col(v).cast(pl.Float32) for v in WEATHER_VARS},
    )
    daily = (
        df.group_by(day=pl.col("ts").dt.date(), year=pl.col("ts").dt.year())
        .agg(rad=pl.col("shortwave_radiation").sum())
        .with_columns(
            hi=pl.col("rad").quantile(0.75).over("year"), lo=pl.col("rad").quantile(0.25).over("year")
        )
        .select(
            "day", is_sunny_day=pl.col("rad") >= pl.col("hi"), is_cloudy_day=pl.col("rad") <= pl.col("lo")
        )
    )
    return (
        df.with_columns(day=pl.col("ts").dt.date())
        .join(daily, on="day", how="left")
        .drop("day")
        .with_columns(hdd15=(15.0 - pl.col("temperature_2m")).clip(lower_bound=0.0).cast(pl.Float32))
        .select(["plz", "ts", *WEATHER_VARS, "is_sunny_day", "is_cloudy_day", "hdd15"])
        .sort("ts")
    )
