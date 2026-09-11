"""Asset-specific commissioning dates for downstream label cleaning, not features."""

from pathlib import Path

import polars as pl

from feature_pipeline.csv_utils import find_column, read_csv_flexible
from feature_pipeline.labels import _LABEL_COLUMNS, _mark_to_flag


def load_gigi_dates(labels_file: Path) -> pl.DataFrame:
    """Coalesce actual dates per positive row, then take the earliest per GP/asset."""
    raw = read_csv_flexible(labels_file, infer_schema_length=0)
    gp_column = find_column(raw.columns, "GP-Nr", "GPNr", "GP Nr")
    if gp_column is None:
        raise ValueError("GIGI labels file has no GP-Nr column")
    dates = []
    for candidate in ("InBetrieb-Datum", "Übergabe", "Datum Unterschrift"):
        column = find_column(raw.columns, candidate)
        if column is not None:
            dates.append(pl.col(column).str.strip_chars().str.strptime(pl.Date, "%d.%m.%Y", strict=False))
    effective = pl.coalesce(dates) if dates else pl.lit(None, dtype=pl.Date)
    values = [pl.col(gp_column).str.strip_chars().cast(pl.Int64, strict=False).alias("gp_nr")]
    for label, candidates in _LABEL_COLUMNS.items():
        column = find_column(raw.columns, *candidates)
        positive = _mark_to_flag(column) == 1 if column is not None else pl.lit(False)
        values.append(
            pl.when(positive)
            .then(effective)
            .otherwise(None)
            .cast(pl.Date)
            .alias(label.replace("label_", "commissioned_", 1))
        )
    return raw.select(values).drop_nulls("gp_nr").group_by("gp_nr").agg(pl.all().min()).sort("gp_nr")
