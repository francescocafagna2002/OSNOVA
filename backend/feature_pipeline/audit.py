"""Minimal built-in audit, printed and saved next to the feature dataset.

Per the brief: no separate diagnostic scripts, the numbers that matter come
out of the main pipeline run.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

import polars as pl

logger = logging.getLogger(__name__)


@dataclass
class AuditReport:
    number_of_consumption_files: int = 0
    number_of_files_processed_this_run: int = 0
    number_of_files_skipped_cached: int = 0
    number_of_files_failed: int = 0
    failed_files: list[str] = field(default_factory=list)

    number_of_mapped_mp_ids: int = 0
    number_of_unmapped_mp_ids: int = 0
    sample_unmapped_mp_ids: list[str] = field(default_factory=list)
    number_of_unresolved_mapping_mp_ids: int = 0
    number_of_ambiguous_mapping_mp_ids: int = 0

    number_of_buildings_in_mapping: int = 0
    number_of_processed_buildings: int = 0
    number_of_multi_mp_buildings: int = 0

    number_of_weather_plz: int = 0
    number_of_building_plz: int = 0
    number_of_building_plz_without_weather: int = 0

    date_range_min: str | None = None
    date_range_max: str | None = None

    nan_counts: dict[str, int] = field(default_factory=dict)

    processing_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def compute_nan_counts(df: pl.DataFrame, exclude: tuple[str, ...] = ("gp_nr", "plz")) -> dict[str, int]:
    counts = {}
    n = df.height
    for col in df.columns:
        if col in exclude:
            continue
        counts[col] = int(df.get_column(col).null_count())
    counts["_total_rows"] = n
    return counts


def write_audit_report(path: Path, report: AuditReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8")


def print_audit_report(report: AuditReport) -> None:
    print("\n=== Feature extraction audit ===")
    print(f"Consumption files:        {report.number_of_consumption_files} "
          f"(processed this run: {report.number_of_files_processed_this_run}, "
          f"cached/skipped: {report.number_of_files_skipped_cached}, "
          f"failed: {report.number_of_files_failed})")
    print(f"Mapped MP IDs:            {report.number_of_mapped_mp_ids}")
    print(f"Unmapped MP IDs:          {report.number_of_unmapped_mp_ids} "
          f"(sample: {report.sample_unmapped_mp_ids[:5]})")
    print(f"Mapping MP IDs dropped:   {report.number_of_unresolved_mapping_mp_ids} unresolved, "
          f"{report.number_of_ambiguous_mapping_mp_ids} ambiguous (see mapping.py)")
    print(f"Buildings in mapping:     {report.number_of_buildings_in_mapping}")
    print(f"Buildings processed:      {report.number_of_processed_buildings}")
    print(f"Multi-MP buildings:       {report.number_of_multi_mp_buildings}")
    print(f"Weather PLZ available:    {report.number_of_weather_plz}")
    print(f"Building PLZ total:       {report.number_of_building_plz} "
          f"(without weather match: {report.number_of_building_plz_without_weather})")
    print(f"Date range:               {report.date_range_min} .. {report.date_range_max}")
    print(f"Processing time:          {report.processing_time_seconds:.1f}s")
    top_nan = sorted(
        ((k, v) for k, v in report.nan_counts.items() if k != "_total_rows"),
        key=lambda kv: kv[1],
        reverse=True,
    )[:10]
    total_rows = report.nan_counts.get("_total_rows", 0)
    print(f"Top NaN columns (of {total_rows} building rows):")
    for col, cnt in top_nan:
        print(f"  {col}: {cnt}")
    print("================================\n")
