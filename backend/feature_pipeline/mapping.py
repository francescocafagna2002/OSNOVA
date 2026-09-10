"""MP ID -> GP-Nr (building) mapping.

Join chain, per the brief:

    MP ID -> Zählpunktbezeichnung (mpid_zähler_mapping.csv)
          -> GPartner / GP-Nr      (Zähler-GP.csv)

Centralises the one fact the rest of the pipeline needs: which meters belong
to which building, and how many meters each building has
(``num_mp_ids``, the audit column the brief asks for).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import polars as pl

from feature_pipeline.config import PathsConfig
from feature_pipeline.csv_utils import find_column, read_csv_flexible

logger = logging.getLogger(__name__)


@dataclass
class MappingResult:
    # mp_id (str) -> gp_nr (str), one row per MP ID.
    mp_to_building: pl.DataFrame
    # gp_nr (str) -> num_mp_ids (u32).
    building_mp_counts: pl.DataFrame
    # MP IDs present in the mapping input files that could not be resolved to
    # exactly one GP-Nr (ambiguous or unresolved joins). Kept for the audit
    # report; these MPs are dropped from ``mp_to_building``.
    dropped_mp_ids: list[str]
    # The same set, split by reason, for a more precise audit report.
    unresolved_mp_ids: list[str]
    ambiguous_mp_ids: list[str]


def load_mapping(paths: PathsConfig) -> MappingResult:
    mp_zp = read_csv_flexible(paths.mp_mapping_file)
    zp_gp = read_csv_flexible(paths.zaehler_gp_file)

    mp_col = find_column(mp_zp.columns, "MP ID", "MP-ID", "MPID")
    zp_col_a = find_column(mp_zp.columns, "Zählpunktbezeichnung", "Zaehlpunktbezeichnung")
    if mp_col is None or zp_col_a is None:
        raise ValueError(
            f"mpid_zähler_mapping.csv: expected 'MP ID' and 'Zählpunktbezeichnung' "
            f"columns, found {mp_zp.columns!r}"
        )

    zp_col_b = find_column(zp_gp.columns, "Zählpunktbezeichnung", "Zaehlpunktbezeichnung")
    gp_col = find_column(zp_gp.columns, "GPartner", "GP-Nr", "GPNr")
    if zp_col_b is None or gp_col is None:
        raise ValueError(
            f"Zähler-GP.csv: expected 'Zählpunktbezeichnung' and 'GPartner' "
            f"columns, found {zp_gp.columns!r}"
        )

    mp_zp = mp_zp.select(
        pl.col(mp_col).cast(pl.Utf8).str.strip_chars().alias("mp_id"),
        pl.col(zp_col_a).cast(pl.Utf8).str.strip_chars().alias("zaehlpunkt"),
    )
    zp_gp = zp_gp.select(
        pl.col(zp_col_b).cast(pl.Utf8).str.strip_chars().alias("zaehlpunkt"),
        pl.col(gp_col).cast(pl.Utf8).str.strip_chars().alias("gp_nr"),
    )

    joined = mp_zp.join(zp_gp, on="zaehlpunkt", how="left")

    unresolved = joined.filter(pl.col("gp_nr").is_null())
    dropped: list[str] = unresolved.get_column("mp_id").to_list()
    if dropped:
        logger.warning(
            "%d MP ID(s) have no matching GPartner via Zählpunktbezeichnung and are dropped: %s%s",
            len(dropped),
            dropped[:10],
            " ..." if len(dropped) > 10 else "",
        )

    resolved = joined.filter(pl.col("gp_nr").is_not_null())

    # Cardinality check: a real-world MP ID should map to exactly one GPartner.
    # The brief already reports this is verified (0 MPs with >1 building), but
    # we defend against a stray duplicate row in the CSVs rather than silently
    # double-counting a meter under two buildings.
    per_mp_building_count = (
        resolved.group_by("mp_id").agg(pl.col("gp_nr").n_unique().alias("n_gp"))
    )
    ambiguous_mp_ids = (
        per_mp_building_count.filter(pl.col("n_gp") > 1).get_column("mp_id").to_list()
    )
    if ambiguous_mp_ids:
        logger.warning(
            "%d MP ID(s) map to more than one GP-Nr; dropping them from the "
            "cohort rather than guessing which building owns them: %s",
            len(ambiguous_mp_ids),
            ambiguous_mp_ids[:10],
        )
        dropped.extend(ambiguous_mp_ids)
        resolved = resolved.filter(~pl.col("mp_id").is_in(ambiguous_mp_ids))

    # A meter can appear more than once in mpid_zähler_mapping.csv (harmless
    # duplicate rows); keep one mapping per MP ID.
    mp_to_building = resolved.unique(subset=["mp_id"], keep="first").select(
        "mp_id", "gp_nr"
    )

    building_mp_counts = (
        mp_to_building.group_by("gp_nr")
        .agg(pl.col("mp_id").n_unique().alias("num_mp_ids"))
        .sort("gp_nr")
    )

    return MappingResult(
        mp_to_building=mp_to_building,
        building_mp_counts=building_mp_counts,
        dropped_mp_ids=sorted(set(dropped)),
        unresolved_mp_ids=sorted(set(unresolved.get_column("mp_id").to_list())),
        ambiguous_mp_ids=sorted(set(ambiguous_mp_ids)),
    )
