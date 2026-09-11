# src/osnova/io/lastgang.py
"""Per-building time series from the feature_pipeline by_file Parquet.

Layout (design revision 2026-09-11): `<store>/osnova/feature_output/intermediate/by_file/*.parquet`,
one file per source CSV, columns `gp_nr` (i64), `ts` (local naive, interval start), `plz`,
`import_kw`, `export_kw`, `net_kw` (f32, net negative = export), `num_mp_with_data`. Only cohort
buildings are in there, so scanning all files filtered by gp_nr is cheap. The pre-revision layout
(`gp_nr` str, a single net `power_kw`) is still read: export = max(0, -power_kw).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl

from osnova.io.store import DT, F32, I64, STR, Store

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


def gp_nr_expr(col: str = "gp_nr") -> pl.Expr:
    """gp_nr of any dtype (i64, or a string of digits) -> Int64."""
    return pl.col(col).cast(pl.String).str.strip_chars().str.extract(r"(\d+)", 1).cast(I64, strict=False)


def to_gp_nr(value: int | str) -> int:
    return int(str(value).strip())


def scan_by_file(store: Store) -> pl.LazyFrame | None:
    files = by_file_paths(store)
    if not files:
        return None
    return pl.scan_parquet(files).with_columns(gp_nr=gp_nr_expr())


def list_buildings(store: Store) -> list[int]:
    """Distinct gp_nr over all by_file parts, sorted."""
    lf = scan_by_file(store)
    if lf is None:
        return []
    return sorted(lf.select("gp_nr").unique().collect()["gp_nr"].drop_nulls().to_list())


def _series_columns(names: list[str]) -> list[pl.Expr]:
    """Whatever layout the part has -> import_kw, export_kw, net_kw (Float64, null = missing)."""
    if "import_kw" in names and "export_kw" in names:
        imp, exp = pl.col("import_kw").cast(pl.Float64), pl.col("export_kw").cast(pl.Float64)
        net = pl.col("net_kw").cast(pl.Float64) if "net_kw" in names else imp - exp
        return [imp.alias("import_kw"), exp.alias("export_kw"), net.alias("net_kw")]
    net_col = "net_kw" if "net_kw" in names else "power_kw"
    net = pl.col(net_col).cast(pl.Float64)
    return [
        net.clip(lower_bound=0.0).alias("import_kw"),
        (-net).clip(lower_bound=0.0).alias("export_kw"),
        net.alias("net_kw"),
    ]


def _normalise(raw: pl.DataFrame) -> pl.DataFrame:
    """Rows of one building (ts, plz, import/export/net) -> BUILDING_SERIES, one row per ts."""
    has_value = pl.col("net_kw").is_not_null()
    per_ts = raw.group_by("ts").agg(
        [
            pl.when(has_value.any()).then(pl.col(c).sum()).otherwise(None).alias(c)
            for c in ("import_kw", "export_kw", "net_kw")
        ]
        + [pl.col("plz").cast(pl.String).drop_nulls().first().alias("plz")]
    )
    return (
        per_ts.with_columns(
            ts=pl.col("ts").cast(DT),
            import_kw=pl.col("import_kw").fill_null(0.0),
            export_kw=pl.col("export_kw").fill_null(0.0),
            quality=pl.when(has_value).then(pl.lit("ok")).otherwise(pl.lit("missing")),
            net_kw=pl.col("net_kw").fill_null(0.0),
        )
        .select(list(BUILDING_SERIES.keys()))
        .cast(dict(BUILDING_SERIES))
        .sort("ts")
    )


def empty_series() -> pl.DataFrame:
    return pl.DataFrame(schema=BUILDING_SERIES)


def load_building_chunk(store: Store, gp_nrs: Iterable[int | str]) -> dict[int, pl.DataFrame]:
    """One scan of the by_file parts for several buildings -> {gp_nr: BUILDING_SERIES frame}."""
    wanted = [to_gp_nr(g) for g in gp_nrs]
    lf = scan_by_file(store)
    if lf is None or not wanted:
        return {g: empty_series() for g in wanted}
    names = lf.collect_schema().names()
    raw = (
        lf.filter(pl.col("gp_nr").is_in(wanted))
        .select("gp_nr", "ts", pl.col("plz").cast(pl.String), *_series_columns(names))
        .collect()
    )
    parts = raw.partition_by("gp_nr", as_dict=True)
    return {g: _normalise(parts[(g,)].drop("gp_nr")) if (g,) in parts else empty_series() for g in wanted}


def load_building_series(store: Store, gp_nr: int | str) -> pl.DataFrame:
    """One building: ts, import_kw, export_kw, net_kw, plz, quality ("ok" if power present else "missing")."""
    return load_building_chunk(store, [gp_nr])[to_gp_nr(gp_nr)]


__all__ = [
    "BUILDING_SERIES",
    "by_file_dir",
    "by_file_paths",
    "empty_series",
    "feature_dataset_path",
    "feature_output_dir",
    "gp_nr_expr",
    "list_buildings",
    "load_building_chunk",
    "load_building_series",
    "scan_by_file",
    "to_gp_nr",
]
