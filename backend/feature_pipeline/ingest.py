"""Raw wide consumption CSV -> building-level long parquet, streamed per file.

Never materialises the whole cohort in RAM: every source CSV is scanned lazily
with polars, unpivoted, joined to the (small, in-memory) MP->building mapping,
summed to (GP-Nr, timestamp) and sunk straight to a per-file Parquet part under
``intermediate/by_file/``. A JSON manifest records which source files are done
(name, size, mtime) so a re-run skips them — the "checkpoint/resume" the brief
asks for.

Multi-MP aggregation (``cfg.multi_mp_strategy``) and duplicate-row collapsing
(``cfg.duplicate_mp_timestamp_strategy``) both happen here, in exactly one
place, so a future change of strategy does not need to touch feature code.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from feature_pipeline.config import PathsConfig, ThresholdsConfig
from feature_pipeline.csv_utils import find_column
from feature_pipeline.timeutil import quarter_hour_columns, quarter_label_to_minutes

logger = logging.getLogger(__name__)

_SUPPORTED_STRATEGIES = {"sum"}


@dataclass
class IngestAudit:
    files_seen: int = 0
    files_processed_this_run: int = 0
    files_skipped_cached: int = 0
    files_failed: list[str] = field(default_factory=list)
    unmapped_mp_ids: set[str] = field(default_factory=set)
    mapped_mp_ids_seen: set[str] = field(default_factory=set)
    min_datum: str | None = None
    max_datum: str | None = None


def discover_consumption_files(paths: PathsConfig) -> list[Path]:
    root = paths.raw_consumption_dir
    if not root.exists():
        return []
    return sorted(p for p in root.glob(paths.raw_consumption_glob) if p.is_file())


def _apply_multi_mp_strategy(strategy: str) -> pl.Expr:
    """The one place ``config.multi_mp_strategy`` is interpreted.

    Add a new branch here (and to ``_SUPPORTED_STRATEGIES``) to change how
    several MPs of the same building are combined; no feature code depends on
    the choice.
    """
    if strategy not in _SUPPORTED_STRATEGIES:
        raise ValueError(
            f"Unknown multi_mp_strategy {strategy!r}; supported: {_SUPPORTED_STRATEGIES}. "
            "Add the new case in feature_pipeline.ingest._apply_multi_mp_strategy."
        )
    return pl.col("power_kw").sum()


def _read_file_schema_names(path: Path) -> list[str]:
    return pl.scan_csv(
        path, separator=";", encoding="utf8-lossy", n_rows=0, infer_schema_length=0
    ).collect_schema().names()


def ingest_one_file(
    path: Path,
    mapping_df: pl.DataFrame,
    thresholds: ThresholdsConfig,
) -> tuple[pl.LazyFrame, set[str]]:
    """Build the lazy (gp_nr, ts, power_kw, plz, num_mp_with_data) frame for one file.

    Returns the lazy frame plus the set of distinct MP IDs seen in the file
    (cheap: cardinality is bounded by meters-per-file, not rows) so the caller
    can accumulate the unmapped-MP-ID audit without touching the row data.
    """
    header = _read_file_schema_names(path)
    quarter_cols = quarter_hour_columns(header)
    if len(quarter_cols) == 0:
        raise ValueError(f"{path}: no 'HH:MM' quarter-hour columns found in header {header!r}")

    mp_col = find_column(header, "MP ID", "MP-ID", "MPID")
    datum_col = find_column(header, "Datum", "Date")
    plz_col = find_column(header, "PLZ", "plz")
    if mp_col is None or datum_col is None:
        raise ValueError(f"{path}: expected 'MP ID' and 'Datum' columns, found {header!r}")

    schema_overrides = {c: pl.Utf8 for c in header}
    lf = pl.scan_csv(
        path,
        separator=";",
        encoding="utf8-lossy",
        infer_schema_length=0,
        schema_overrides=schema_overrides,
    )

    keep_cols = [mp_col, datum_col, *quarter_cols]
    if plz_col is not None:
        keep_cols.append(plz_col)
    lf = lf.select(keep_cols)

    # Distinct MP IDs actually present, for the unmapped-MP audit — collected
    # eagerly here because it is small (bounded by meters-per-file) and lets
    # the caller union it across files without ever touching the row-level data.
    mp_ids_in_file: set[str] = set(
        lf.select(pl.col(mp_col).unique()).collect().get_column(mp_col).drop_nulls().to_list()
    )

    unpivoted = lf.unpivot(
        index=[c for c in keep_cols if c not in quarter_cols],
        on=quarter_cols,
        variable_name="_time_label",
        value_name="power_kw",
    )

    offsets = {label: quarter_label_to_minutes(label) for label in quarter_cols}
    # Map each "HH:MM" label to a fixed offset-in-minutes via a small
    # replace-with-default expression built from the offsets dict.
    minute_expr = pl.col("_time_label").replace_strict(offsets, default=None, return_dtype=pl.Int32)

    unpivoted = unpivoted.with_columns(
        pl.col(datum_col).str.strptime(pl.Date, strict=False).alias("_date"),
        pl.col("power_kw")
        .str.replace(",", ".", literal=True)
        .cast(pl.Float64, strict=False)
        .alias("power_kw"),
        minute_expr.alias("_minute_offset"),
    ).with_columns(
        (
            pl.col("_date").cast(pl.Datetime("us"))
            + pl.duration(minutes=pl.col("_minute_offset"))
        ).alias("ts")
    )

    rename_map = {mp_col: "mp_id"}
    if plz_col is not None:
        rename_map[plz_col] = "plz"
    unpivoted = unpivoted.rename(rename_map)
    if "plz" not in unpivoted.collect_schema().names():
        unpivoted = unpivoted.with_columns(pl.lit(None, dtype=pl.Utf8).alias("plz"))

    # Collapse duplicate raw rows at the exact same (MP ID, timestamp) — e.g. a
    # second OBIS-Code row, which the brief says is not used for this task.
    collapsed = unpivoted.group_by(["mp_id", "ts"]).agg(
        pl.col("power_kw").sum().alias("power_kw"),
        pl.col("plz").drop_nulls().first().alias("plz"),
    )

    joined = collapsed.join(mapping_df.lazy(), on="mp_id", how="inner")

    building = joined.group_by(["gp_nr", "ts"]).agg(
        _apply_multi_mp_strategy(thresholds.multi_mp_strategy).alias("power_kw"),
        pl.col("mp_id").n_unique().alias("num_mp_with_data"),
        pl.col("plz").drop_nulls().first().alias("plz"),
    )

    return building, mp_ids_in_file


def _load_manifest(manifest_path: Path) -> dict:
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"files": {}}


def _save_manifest(manifest_path: Path, manifest: dict) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


def _file_fingerprint(path: Path) -> dict:
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}


def run_ingest(
    paths: PathsConfig,
    thresholds: ThresholdsConfig,
    mapping_df: pl.DataFrame,
    limit_files: int | None = None,
    resume: bool = True,
) -> IngestAudit:
    """Ingest every discovered consumption file into ``intermediate/by_file/``."""
    files = discover_consumption_files(paths)
    if limit_files is not None:
        files = files[:limit_files]

    audit = IngestAudit(files_seen=len(files))
    by_file_dir = paths.by_file_dir
    by_file_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(paths.manifest_path) if resume else {"files": {}}

    for path in files:
        key = str(path)
        fingerprint = _file_fingerprint(path)
        out_path = by_file_dir / f"{path.stem}.parquet"
        cached = manifest["files"].get(key)
        if resume and cached == fingerprint and out_path.exists():
            audit.files_skipped_cached += 1
            continue

        try:
            lf, mp_ids_in_file = ingest_one_file(path, mapping_df, thresholds)
            lf.sink_parquet(out_path)
        except Exception:
            logger.exception("Failed to ingest %s; skipping this file, continuing.", path)
            audit.files_failed.append(key)
            continue

        audit.mapped_mp_ids_seen |= mp_ids_in_file & set(
            mapping_df.get_column("mp_id").to_list()
        )
        audit.unmapped_mp_ids |= mp_ids_in_file - set(mapping_df.get_column("mp_id").to_list())
        manifest["files"][key] = fingerprint
        audit.files_processed_this_run += 1

    _save_manifest(paths.manifest_path, manifest)
    return audit


def scan_building_consumption(paths: PathsConfig) -> pl.LazyFrame:
    """Lazily scan every per-file building-level part and re-sum overlaps.

    A final ``group_by(gp_nr, ts)`` guards against the (unexpected, but not
    impossible) case of the same building+timestamp appearing in two source
    files; when files partition cleanly by month/year this is a no-op.
    """
    parts = sorted(paths.by_file_dir.glob("*.parquet"))
    if not parts:
        raise FileNotFoundError(
            f"No ingested parts under {paths.by_file_dir}; run ingest first."
        )
    lf = pl.scan_parquet(parts)
    return lf.group_by(["gp_nr", "ts"]).agg(
        pl.col("power_kw").sum().alias("power_kw"),
        pl.col("num_mp_with_data").sum().alias("num_mp_with_data"),
        pl.col("plz").drop_nulls().first().alias("plz"),
    )
