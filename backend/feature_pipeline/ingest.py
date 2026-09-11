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

import hashlib
import json
import logging
import random
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import polars as pl

from feature_pipeline.config import CohortConfig, PathsConfig, ThresholdsConfig
from feature_pipeline.csv_utils import find_column
from feature_pipeline.timeutil import quarter_hour_columns, quarter_label_to_minutes

logger = logging.getLogger(__name__)

_SUPPORTED_STRATEGIES = {"sum"}


def select_cohort(mapping: pl.DataFrame, labels: pl.DataFrame, cfg: CohortConfig) -> pl.DataFrame:
    """Select known, linked GPs and a reproducible sample of other Table 4 GPs."""
    mapping = mapping.with_columns(pl.col("gp_nr").cast(pl.Int64, strict=False)).drop_nulls("gp_nr")
    labels = labels.with_columns(pl.col("gp_nr").cast(pl.Int64, strict=False)).drop_nulls("gp_nr")
    flags = ["label_pv", "label_ev", "label_heatpump", "label_battery"]
    linked = mapping.filter(pl.col("mp_id").is_not_null()).select("gp_nr").unique()
    known = labels.filter(pl.any_horizontal(pl.col(flags).is_not_null()))
    labeled = known.select("gp_nr").unique().join(linked, on="gp_nr", how="semi")
    labeled_ids = set(labeled["gp_nr"].to_list())
    others = sorted(set(mapping["gp_nr"].to_list()) - labeled_ids)
    count = 0 if cfg.labeled_only else min(cfg.extra_random_gps, len(others))
    selected_ids = labeled_ids | set(random.Random(cfg.seed).sample(others, count))
    mapped_ids = set(mapping["gp_nr"].to_list())
    for gp in cfg.include_gps:
        if gp in mapped_ids:
            selected_ids.add(int(gp))
        else:
            logger.warning("include_gps: GP %s is not in the MP mapping (Table 4); skipped", gp)
    selected = sorted(selected_ids)
    cohort = pl.DataFrame({"gp_nr": selected}, schema={"gp_nr": pl.Int64}).with_columns(
        pl.col("gp_nr").is_in(sorted(labeled_ids)).alias("is_labeled")
    )
    postal_frames = [
        frame.select("gp_nr", pl.col("plz").cast(pl.String))
        for frame in (labels, mapping)
        if "plz" in frame.columns
    ]
    if postal_frames:
        postal = (
            pl.concat(postal_frames)
            .group_by("gp_nr")
            .agg(pl.col("plz").str.strip_chars().replace("", None).drop_nulls().sort().first())
        )
        cohort = cohort.join(postal, on="gp_nr", how="left")
    else:
        cohort = cohort.with_columns(pl.lit(None, dtype=pl.String).alias("plz"))
    return cohort.select("gp_nr", "is_labeled", "plz").sort("gp_nr")


@dataclass
class IngestAudit:
    parts: list[Path] = field(default_factory=list)
    rows_per_part: dict[str, int] = field(default_factory=dict)
    ignored_obis_rows: Counter[str] = field(default_factory=Counter)
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


def _apply_multi_mp_strategy(strategy: str, column: str = "power_kw") -> pl.Expr:
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
    return pl.when(pl.col(column).count() == pl.len()).then(pl.col(column).sum()).otherwise(None)


def _read_file_schema_names(path: Path) -> list[str]:
    return (
        pl.scan_csv(path, separator=";", encoding="utf8-lossy", n_rows=0, infer_schema_length=0)
        .collect_schema()
        .names()
    )


def ingest_one_file(
    path: Path,
    mapping_df: pl.DataFrame,
    thresholds: ThresholdsConfig,
    cohort: pl.DataFrame | None = None,
    audit: IngestAudit | None = None,
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
    obis_col = find_column(header, "OBIS-Code")
    if mp_col is None or datum_col is None or obis_col is None:
        raise ValueError(f"{path}: expected 'MP ID', 'Datum' and 'OBIS-Code' columns, found {header!r}")

    schema_overrides = {c: pl.Utf8 for c in header}
    lf = pl.scan_csv(
        path,
        separator=";",
        encoding="utf8-lossy",
        infer_schema_length=0,
        schema_overrides=schema_overrides,
    )

    keep_cols = [mp_col, datum_col, obis_col, *quarter_cols]
    if plz_col is not None:
        keep_cols.append(plz_col)
    lf = lf.select(keep_cols).with_columns(pl.col(mp_col).str.strip_chars())

    obis = pl.col(obis_col).str.strip_chars().replace("", None).fill_null("<missing>")
    observed = (
        lf.select(
            pl.col(mp_col).drop_nulls().unique().implode().alias("mp_ids"),
            obis.filter(~obis.is_in([thresholds.import_obis, thresholds.export_obis]))
            .alias("code")
            .value_counts(name="rows")
            .implode()
            .alias("ignored_obis"),
        )
        .collect(engine="streaming")
        .row(0, named=True)
    )
    mp_ids_in_file = set(observed["mp_ids"])
    if audit is not None:
        audit.ignored_obis_rows.update({entry["code"]: entry["rows"] for entry in observed["ignored_obis"]})

    mapping_df = (
        mapping_df.select("mp_id", pl.col("gp_nr").cast(pl.Int64, strict=False)).drop_nulls().unique()
    )
    if cohort is not None:
        mapping_df = mapping_df.join(cohort.select("gp_nr"), on="gp_nr", how="semi")
    mapping_df = mapping_df.with_columns(pl.len().over("gp_nr").alias("_expected_mp"))
    lf = lf.join(mapping_df.lazy(), left_on=mp_col, right_on="mp_id", how="inner").filter(
        pl.col(obis_col).str.strip_chars().is_in([thresholds.import_obis, thresholds.export_obis])
    )
    unpivoted = lf.unpivot(
        index=[c for c in keep_cols if c not in quarter_cols] + ["gp_nr", "_expected_mp"],
        on=quarter_cols,
        variable_name="_time_label",
        value_name="power_kw",
    )

    offsets = {
        label: (quarter_label_to_minutes(label) - thresholds.interval_minutes) % (24 * 60)
        for label in quarter_cols
    }
    # Map each "HH:MM" label to a fixed offset-in-minutes via a small
    # replace-with-default expression built from the offsets dict.
    minute_expr = pl.col("_time_label").replace_strict(offsets, default=None, return_dtype=pl.Int32)

    unpivoted = unpivoted.with_columns(
        pl.col(datum_col)
        .str.strip_chars()
        .str.strptime(pl.Date, thresholds.date_format, strict=True)
        .alias("_date"),
        (
            pl.col("power_kw")
            .str.strip_chars()
            .str.replace(",", ".", literal=True)
            .cast(pl.Float64, strict=False)
            * thresholds.unit_factor
        )
        .fill_nan(None)
        .alias("power_kw"),
        minute_expr.alias("_minute_offset"),
    ).with_columns(
        (pl.col("_date").cast(pl.Datetime("us")) + pl.duration(minutes=pl.col("_minute_offset"))).alias("ts")
    )

    rename_map = {mp_col: "mp_id"}
    if plz_col is not None:
        rename_map[plz_col] = "plz"
    unpivoted = unpivoted.rename(rename_map)
    if "plz" not in unpivoted.collect_schema().names():
        unpivoted = unpivoted.with_columns(pl.lit(None, dtype=pl.Utf8).alias("plz"))

    def channel(code: str) -> pl.Expr:
        values = pl.col("power_kw").filter(pl.col(obis_col).str.strip_chars() == code)
        total = (
            pl.when((values.len() > 0) & (values.count() == values.len())).then(values.sum()).otherwise(None)
        )
        if code == thresholds.export_obis:
            return pl.when(values.len() == 0).then(0.0).otherwise(total)
        return total

    if thresholds.duplicate_mp_timestamp_strategy not in _SUPPORTED_STRATEGIES:
        raise ValueError("Unsupported duplicate_mp_timestamp_strategy")
    collapsed = (
        unpivoted.group_by(["gp_nr", "mp_id", "ts"])
        .agg(
            channel(thresholds.import_obis).alias("import_kw"),
            channel(thresholds.export_obis).alias("export_kw"),
            pl.col("_expected_mp").first(),
            pl.col("plz").drop_nulls().first().alias("plz"),
        )
        .with_columns((pl.col("import_kw") - pl.col("export_kw")).alias("net_kw"))
    )

    building = (
        collapsed.group_by(["gp_nr", "ts"])
        .agg(
            *[
                pl.when(pl.len() == pl.col("_expected_mp").first())
                .then(_apply_multi_mp_strategy(thresholds.multi_mp_strategy, column))
                .otherwise(None)
                .alias(column)
                for column in ("import_kw", "export_kw", "net_kw")
            ],
            pl.col("mp_id").filter(pl.col("net_kw").is_not_null()).n_unique().alias("num_mp_with_data"),
            pl.col("plz").drop_nulls().first().alias("plz"),
        )
        .with_columns(pl.col("import_kw", "export_kw").cast(pl.Float32))
        .with_columns((pl.col("import_kw") - pl.col("export_kw")).alias("net_kw"))
        .with_columns(pl.col("net_kw").alias("power_kw"))
        .select("gp_nr", "ts", "import_kw", "export_kw", "net_kw", "power_kw", "plz", "num_mp_with_data")
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
    cohort: pl.DataFrame | None = None,
) -> IngestAudit:
    """Ingest every discovered consumption file into ``intermediate/by_file/``."""
    files = discover_consumption_files(paths)
    if limit_files is not None:
        if limit_files < 1:
            raise ValueError("limit_files must be positive")
        files = files[:limit_files]
    if not files:
        raise FileNotFoundError(f"No consumption files under {paths.raw_consumption_dir}")

    audit = IngestAudit(files_seen=len(files))
    by_file_dir = paths.by_file_dir
    by_file_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {
        path: by_file_dir
        / f"{path.stem}_{hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]}.parquet"
        for path in files
    }
    if set(by_file_dir.glob("*.parquet")) - set(output_paths.values()):
        raise ValueError(
            "Existing by_file parts are outside the current selection; use a new output directory"
        )
    manifest = _load_manifest(paths.manifest_path) if resume else {"files": {}}
    identity = {
        "version": 4,
        "thresholds": asdict(thresholds),
        "mapping": mapping_df.sort(["gp_nr", "mp_id"]).to_dicts(),
        "cohort": cohort.sort("gp_nr").to_dicts() if cohort is not None else None,
    }
    config_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if manifest["files"] and manifest.get("config_hash") != config_hash:
        raise ValueError("Ingest configuration changed; use a new output directory or --no-resume")
    manifest["config_hash"] = config_hash

    # Computed once, not per file: the full MP-id set (for the unmapped-MP
    # audit) and a running "distinct buildings covered so far" count, so a
    # long ingest run (the slow step on the real 90k-building dataset) prints
    # visible progress instead of going quiet for minutes.
    all_mapped_mp_ids = set(mapping_df.get_column("mp_id").to_list())
    total_buildings = cohort.height if cohort is not None else mapping_df.get_column("gp_nr").n_unique()
    buildings_seen: set[int] = set()

    for i, path in enumerate(files, start=1):
        key = str(path)
        fingerprint = _file_fingerprint(path)
        out_path = output_paths[path]
        cached = manifest["files"].get(key)
        if resume and cached and cached.get("fingerprint") == fingerprint and out_path.exists():
            audit.files_skipped_cached += 1
            audit.ignored_obis_rows.update(cached["ignored_obis_rows"])
            mp_ids_in_file = set(cached["mp_ids"])
            audit.mapped_mp_ids_seen |= mp_ids_in_file & all_mapped_mp_ids
            audit.unmapped_mp_ids |= mp_ids_in_file - all_mapped_mp_ids
            audit.parts.append(out_path)
            audit.rows_per_part[str(out_path)] = int(
                pl.scan_parquet(out_path).select(pl.len()).collect().item()
            )
            # Still worth folding into the running building count: cheap,
            # since the per-file parquet already has the distinct gp_nrs.
            buildings_seen |= set(
                pl.scan_parquet(out_path).select("gp_nr").unique().collect().get_column("gp_nr")
            )
            logger.info(
                "[%d/%d] cached, skipping %s — rows: %d; buildings covered so far: %d/%d",
                i,
                len(files),
                path.name,
                audit.rows_per_part[str(out_path)],
                len(buildings_seen),
                total_buildings,
            )
            continue

        try:
            file_audit = IngestAudit()
            lf, mp_ids_in_file = ingest_one_file(
                path, mapping_df, thresholds, cohort=cohort, audit=file_audit
            )
            partial = out_path.with_suffix(".partial")
            lf.sink_parquet(partial)
            partial.replace(out_path)
        except Exception as error:
            audit.files_failed.append(key)
            raise RuntimeError(f"Failed to ingest {path}; no final feature dataset produced") from error

        audit.mapped_mp_ids_seen |= mp_ids_in_file & all_mapped_mp_ids
        audit.unmapped_mp_ids |= mp_ids_in_file - all_mapped_mp_ids
        audit.ignored_obis_rows.update(file_audit.ignored_obis_rows)
        manifest["files"][key] = {
            "fingerprint": fingerprint,
            "mp_ids": sorted(mp_ids_in_file),
            "ignored_obis_rows": dict(file_audit.ignored_obis_rows),
        }
        audit.parts.append(out_path)
        audit.rows_per_part[str(out_path)] = int(pl.scan_parquet(out_path).select(pl.len()).collect().item())
        audit.files_processed_this_run += 1
        _save_manifest(paths.manifest_path, manifest)

        buildings_seen |= set(
            pl.scan_parquet(out_path).select("gp_nr").unique().collect().get_column("gp_nr")
        )
        logger.info(
            "[%d/%d] ingested %s (%d MP ids seen) — rows: %d; buildings covered so far: %d/%d",
            i,
            len(files),
            path.name,
            len(mp_ids_in_file),
            audit.rows_per_part[str(out_path)],
            len(buildings_seen),
            total_buildings,
        )

    _save_manifest(paths.manifest_path, manifest)
    return audit


def scan_building_consumption(paths: PathsConfig, parts: list[Path] | None = None) -> pl.LazyFrame:
    """Lazily scan every per-file building-level part and re-sum overlaps.

    A final ``group_by(gp_nr, ts)`` guards against the (unexpected, but not
    impossible) case of the same building+timestamp appearing in two source
    files; when files partition cleanly by month/year this is a no-op.
    """
    parts = sorted(paths.by_file_dir.glob("*.parquet")) if parts is None else parts
    if not parts:
        raise FileNotFoundError(f"No ingested parts under {paths.by_file_dir}; run ingest first.")
    lf = pl.scan_parquet(parts)
    return (
        lf.group_by(["gp_nr", "ts"])
        .agg(
            *[
                _apply_multi_mp_strategy("sum", column).alias(column)
                for column in ("import_kw", "export_kw", "net_kw")
            ],
            pl.col("num_mp_with_data").sum().alias("num_mp_with_data"),
            pl.col("plz").drop_nulls().first().alias("plz"),
        )
        .with_columns(pl.col("net_kw").alias("power_kw"))
    )
