# src/osnova/io/lastgang.py
"""Per-building time series from the feature_pipeline by_file Parquet.

Layout: `<store>/osnova/feature_output/intermediate/by_file/*.parquet`, one file per source CSV,
columns `gp_nr` (str), `ts` (local naive, interval start), `power_kw` (net, negative = export),
`plz`, `num_mp_with_data`. Only cohort buildings are in there, so scanning all files filtered by
gp_nr is cheap. There is no separate export channel: export = max(0, -power_kw).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl

from osnova.io.store import DT, F32, STR, Store

BUILDING_SERIES = pl.Schema(
    {"ts": DT, "import_kw": F32, "export_kw": F32, "net_kw": F32, "plz": STR, "quality": STR}
)


def feature_output_dir(store: Store) -> Path:
    return store.root / "feature_output"


def by_file_dir(store: Store) -> Path:
    return feature_output_dir(store) / "intermediate" / "by_file"


def feature_dataset_path(store: Store) -> Path:
    return feature_output_dir(store) / "feature_dataset.parquet"


def by_file_paths(store: Store) -> list[Path]:
    return sorted(by_file_dir(store).glob("*.parquet"))


def scan_by_file(store: Store) -> pl.LazyFrame | None:
    files = by_file_paths(store)
    if not files:
        return None
    return pl.scan_parquet(files).with_columns(pl.col("gp_nr").cast(pl.String).str.strip_chars())


def list_buildings(store: Store) -> list[str]:
    """Distinct gp_nr over all by_file parts, sorted."""
    lf = scan_by_file(store)
    if lf is None:
        return []
    return sorted(lf.select("gp_nr").unique().collect()["gp_nr"].drop_nulls().to_list())


def _normalise(raw: pl.DataFrame) -> pl.DataFrame:
    """Rows of one building (gp_nr, ts, power_kw, plz) -> BUILDING_SERIES, one row per ts."""
    has_value = pl.col("power_kw").is_not_null()
    per_ts = raw.group_by("ts").agg(
        power_kw=pl.when(has_value.any()).then(pl.col("power_kw").sum()).otherwise(None),
        plz=pl.col("plz").cast(pl.String).drop_nulls().first(),
    )
    net = pl.col("power_kw").fill_null(0.0)
    return (
        per_ts.with_columns(
            ts=pl.col("ts").cast(DT),
            import_kw=net.clip(lower_bound=0.0),
            export_kw=(-net).clip(lower_bound=0.0),
            net_kw=net,
            quality=pl.when(has_value).then(pl.lit("ok")).otherwise(pl.lit("missing")),
        )
        .select(list(BUILDING_SERIES.keys()))
        .cast(dict(BUILDING_SERIES))
        .sort("ts")
    )


def empty_series() -> pl.DataFrame:
    return pl.DataFrame(schema=BUILDING_SERIES)


def load_building_chunk(store: Store, gp_nrs: Iterable[str]) -> dict[str, pl.DataFrame]:
    """One scan of the by_file parts for several buildings -> {gp_nr: BUILDING_SERIES frame}."""
    wanted = [str(g) for g in gp_nrs]
    lf = scan_by_file(store)
    if lf is None or not wanted:
        return {g: empty_series() for g in wanted}
    raw = lf.filter(pl.col("gp_nr").is_in(wanted)).select(["gp_nr", "ts", "power_kw", "plz"]).collect()
    parts = raw.partition_by("gp_nr", as_dict=True)
    return {g: _normalise(parts[(g,)].drop("gp_nr")) if (g,) in parts else empty_series() for g in wanted}


def load_building_series(store: Store, gp_nr: str) -> pl.DataFrame:
    """One building: ts, import_kw, export_kw, net_kw, plz, quality ("ok" if power present else "missing")."""
    return load_building_chunk(store, [str(gp_nr)])[str(gp_nr)]


__all__ = [
    "BUILDING_SERIES",
    "by_file_dir",
    "by_file_paths",
    "empty_series",
    "feature_dataset_path",
    "feature_output_dir",
    "list_buildings",
    "load_building_chunk",
    "load_building_series",
    "scan_by_file",
]
