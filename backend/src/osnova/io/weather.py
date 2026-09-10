# src/osnova/io/weather.py
"""Weather: find the Open-Meteo files, normalise them to the WEATHER schema, and upsample to 15 min.

Real layout (ERA5 download on Renku): `<weather_dir>/weather_part_N/hourly/<PLZ>/<YYYY-MM>.csv.gz`,
comma-separated, columns `PLZ, timestamp_utc, <variables>`, UTC hours. The pipeline stores local naive
`Europe/Zurich` interval starts, so timestamps are converted and the previous-hour variables
(radiation, sunshine, precipitation, snowfall) are relabelled from interval end to interval start.
A plain Open-Meteo export with a local `time` column (one file per PLZ) is accepted too.
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path

import polars as pl

from osnova.config import Config
from osnova.io.store import WEATHER, WEATHER_VARS, Store

INTERPOLATED: tuple[str, ...] = ("temperature_2m",)
WEATHER_MARKER = "temperature_2m"  # a weather CSV is any csv/csv.gz whose header has this column


# --------------------------------------------------------------------------- files


def first_line(path: Path) -> str:
    """Header line of a csv or csv.gz, decoded leniently."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:  # type: ignore[operator]
        raw = fh.readline()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def find_weather_files(weather_dir: Path) -> list[Path]:
    """Weather CSVs at any depth, recognised by header; coordinates csv, zips and json sidecars skipped."""
    if not weather_dir.exists():
        return []
    out: list[Path] = []
    for p in sorted(weather_dir.rglob("*")):
        if p.is_file() and (p.name.endswith(".csv") or p.name.endswith(".csv.gz")):
            if WEATHER_MARKER in first_line(p):
                out.append(p)
    return out


def plz_of_weather_file(path: Path, df: pl.DataFrame | None = None) -> str | None:
    """`hourly/<plz>/<month>.csv.gz` -> parent dir; else the PLZ column; else 4 digits in the file name."""
    if path.parent.name.isdigit():
        return path.parent.name
    if df is not None:
        col = next((c for c in df.columns if c.lower() == "plz"), None)
        if col is not None and df.height:
            return str(df[col][0]).strip()
    m = re.search(r"(?<!\d)(\d{4})(?!\d)", path.name.split(".")[0])
    return m.group(1) if m else None


def group_files_by_plz(files: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {}
    for p in files:
        plz = plz_of_weather_file(p) or plz_of_weather_file(p, read_raw(p)) or "unknown"
        groups.setdefault(plz, []).append(p)
    return groups


def read_raw(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, infer_schema_length=0, encoding="utf8-lossy")  # gz is transparent


# --------------------------------------------------------------------------- normalise


def _raw_to_hourly(path: Path, cfg: Config) -> pl.DataFrame:
    """One file -> columns plz, ts_sort (real-time order), ts (local naive), WEATHER_VARS as Float32."""
    df = read_raw(path)
    wc = cfg.weather
    plz = plz_of_weather_file(path, df)
    if plz is None:
        raise ValueError(f"cannot determine PLZ of weather file {path}")
    utc_col = next((c for c in df.columns if c.lower() == wc.utc_time_column), None)
    local_col = next((c for c in df.columns if c.lower() == wc.local_time_column), None)
    if utc_col is not None:
        ts_utc = (
            pl.col(utc_col).str.strip_chars().str.to_datetime(time_unit="ms", time_zone="UTC", strict=False)
        )
        ts_expr = ts_utc.dt.convert_time_zone(wc.timezone).dt.replace_time_zone(None)
        sort_expr = ts_utc.dt.replace_time_zone(None)
    elif local_col is not None:
        ts_expr = pl.col(local_col).str.strip_chars().str.to_datetime(time_unit="ms", strict=False)
        sort_expr = ts_expr
    else:
        raise ValueError(f"{path}: no {wc.utc_time_column!r} or {wc.local_time_column!r} column")
    values = [
        (
            pl.col(v).str.strip_chars().cast(pl.Float32, strict=False)
            if v in df.columns
            else pl.lit(None, pl.Float32)
        ).alias(v)
        for v in WEATHER_VARS
    ]
    return df.select(
        pl.lit(plz).alias("plz"),
        sort_expr.cast(pl.Datetime("ms")).alias("ts_sort"),
        ts_expr.cast(pl.Datetime("ms")).alias("ts"),
        *values,
    ).drop_nulls(["ts"])


def _normalize_plz(hourly: pl.DataFrame, cfg: Config) -> pl.DataFrame:
    """Concatenated raw hours of ONE plz -> WEATHER frame (sorted, unique local ts, flags, hdd15)."""
    fc = cfg.features
    df = hourly.sort("ts_sort")
    # previous-hour variables: value at row t describes (t-1h, t] -> move to the row before, keep last
    shift = [
        pl.col(v).shift(-1).fill_null(pl.col(v)).alias(v)
        for v in cfg.weather.end_labelled_vars
        if v in df.columns
    ]
    df = df.with_columns(shift).unique(subset=["ts"], keep="first", maintain_order=True).drop("ts_sort")
    daily = (
        df.group_by(day=pl.col("ts").dt.date(), year=pl.col("ts").dt.year())
        .agg(rad=pl.col("shortwave_radiation").sum())
        .with_columns(
            hi=pl.col("rad").quantile(fc.sunny_quantile).over("year"),
            lo=pl.col("rad").quantile(fc.cloudy_quantile).over("year"),
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
        .select(list(WEATHER.keys()))
        .cast(dict(WEATHER))
        .sort("ts")
    )


def normalize_weather_all(files: list[Path], cfg: Config) -> dict[str, pl.DataFrame]:
    """All files (any number of PLZ, any number of months) -> {plz: WEATHER frame}."""
    raw = [_raw_to_hourly(p, cfg) for p in files]
    if not raw:
        return {}
    out: dict[str, pl.DataFrame] = {}
    for (plz,), part in pl.concat(raw).partition_by("plz", as_dict=True).items():
        out[str(plz)] = _normalize_plz(part, cfg)
    return out


def normalize_weather(path: Path, cfg: Config) -> pl.DataFrame:
    """One file holding one PLZ -> WEATHER frame."""
    by_plz = normalize_weather_all([path], cfg)
    if len(by_plz) != 1:
        raise ValueError(f"{path}: expected one PLZ, found {sorted(by_plz)}")
    return next(iter(by_plz.values()))


# --------------------------------------------------------------------------- store


def write_weather(store: Store, by_plz: dict[str, pl.DataFrame]) -> dict[str, int]:
    store.weather_dir().mkdir(parents=True, exist_ok=True)
    rows: dict[str, int] = {}
    for plz, df in by_plz.items():
        df.write_parquet(store.weather_path(plz))
        rows[plz] = df.height
    return rows


def load_weather(store: Store, plz: str) -> pl.DataFrame | None:
    path = store.weather_path(plz)
    return pl.read_parquet(path) if path.exists() else None


# --------------------------------------------------------------------------- upsample


def upsample_15min(hourly: pl.DataFrame) -> pl.DataFrame:
    """Hourly rows of ONE plz -> 15-minute rows. Temperature linear, other columns forward-filled."""
    if hourly.height == 0:
        return hourly
    value_cols = [c for c in hourly.columns if c not in ("plz", "ts")]
    plz = hourly["plz"][0]
    grid = pl.DataFrame({"ts": pl.datetime_range(hourly["ts"].min(), hourly["ts"].max(), "15m", eager=True)})
    grid = grid.with_columns(ts=pl.col("ts").cast(hourly.schema["ts"]))
    out = grid.join(hourly.drop("plz"), on="ts", how="left").sort("ts")
    exprs = [pl.col(c).interpolate() if c in INTERPOLATED else pl.col(c).forward_fill() for c in value_cols]
    return out.with_columns(exprs).with_columns(plz=pl.lit(plz)).select(["plz", "ts", *value_cols])


__all__ = [
    "WEATHER_VARS",
    "find_weather_files",
    "first_line",
    "group_files_by_plz",
    "load_weather",
    "normalize_weather",
    "normalize_weather_all",
    "plz_of_weather_file",
    "upsample_15min",
    "write_weather",
]
