"""Known device labels, aggregated to one row per GP-Nr.

Source: ``HackDays2026 - GIGI.csv`` (~1192 rows, 878 unique GP-Nr — a building
can appear more than once). Per the brief, a device column cell means:

    "x"/"X"  -> device present
    "-"      -> device confirmed absent
    blank    -> unknown

Aggregation per GP-Nr: any "x" -> 1; else any "-" -> 0; else null.

Only the four device flag columns are used here. ``PV-Leistung in kWp`` and
the commissioning-date columns are intentionally **not** read into features
anywhere in this package (target leakage / out of scope for this task).
"""

from __future__ import annotations

import polars as pl

from feature_pipeline.config import PathsConfig
from feature_pipeline.csv_utils import find_column, read_csv_flexible

# (source column candidates, output label column)
_LABEL_COLUMNS = {
    "label_pv": ("PV",),
    "label_ev": ("Ladestation für Elektrofahrzeuge", "Ladestation fuer Elektrofahrzeuge"),
    "label_heatpump": ("WärmePumpe", "Waermepumpe", "Wärmepumpe"),
    "label_battery": ("Batterie/Speicher", "Batterie / Speicher"),
}


def _mark_to_flag(col: str) -> pl.Expr:
    stripped = pl.col(col).cast(pl.Utf8).str.strip_chars()
    return (
        pl.when(stripped.str.to_lowercase() == "x")
        .then(pl.lit(1, dtype=pl.Int8))
        .when(stripped == "-")
        .then(pl.lit(0, dtype=pl.Int8))
        .otherwise(pl.lit(None, dtype=pl.Int8))
    )


def _aggregate_flag(flag_col: str) -> pl.Expr:
    # any 1 -> 1; else any 0 -> 0; else null. max() over {0,1} with nulls
    # ignored already implements "any 1 wins"; we only need to special-case
    # "all null" (no information at all) vs "all-null-or-zero" (confirmed 0).
    has_any_info = pl.col(flag_col).is_not_null().any()
    return (
        pl.when(~has_any_info)
        .then(pl.lit(None, dtype=pl.Int8))
        .otherwise(pl.col(flag_col).max())
    )


def load_labels(paths: PathsConfig) -> pl.DataFrame:
    raw = read_csv_flexible(paths.labels_file)

    gp_col = find_column(raw.columns, "GP-Nr", "GPNr", "GP Nr")
    if gp_col is None:
        raise ValueError(f"GIGI labels file: expected a 'GP-Nr' column, found {raw.columns!r}")

    select_exprs = [pl.col(gp_col).cast(pl.Utf8).str.strip_chars().alias("gp_nr")]
    present_flag_cols: list[str] = []
    for label_col, candidates in _LABEL_COLUMNS.items():
        src = find_column(raw.columns, *candidates)
        if src is None:
            # Missing column entirely -> every building is "unknown" for this
            # label; still emit the column so the schema is stable.
            select_exprs.append(pl.lit(None, dtype=pl.Int8).alias(label_col))
            continue
        select_exprs.append(_mark_to_flag(src).alias(label_col))
        present_flag_cols.append(label_col)

    per_row = raw.select(select_exprs)

    agg_exprs = [_aggregate_flag(c).alias(c) for c in _LABEL_COLUMNS]
    labels = per_row.group_by("gp_nr").agg(agg_exprs)
    return labels
