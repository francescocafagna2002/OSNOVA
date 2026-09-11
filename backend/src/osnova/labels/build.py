# src/osnova/labels/build.py
"""Training labels, one row per building (gp_nr) and asset.

Inputs are the feature table of ``feature_pipeline`` (``label_<asset>`` flags as 1 / 0 / null) and the
GIGI commissioning dates (``commissioned_<asset>``, Date, nullable). Rules per building and asset:

- flag 1 and (no date or date <= cutoff)  -> positive, weight 1, source ``registry``
- flag 1 and date > cutoff                -> no row (installed too late to be visible in the window)
- flag 0 (explicit "-" in GIGI)           -> negative, weight ``registry_negative_weight``, ``registry``
- flag null, other flags known            -> no row (unknown)
- every flag null (not in GIGI)           -> negative, weight ``unlabeled_weight``, source ``unlabeled``
"""

from __future__ import annotations

from datetime import date

import polars as pl

from osnova.config import ASSETS, LabelConfig
from osnova.io.store import LABELS

# feature-table flag column and GIGI date column per asset (heat_pump <-> heatpump)
FLAG_COLUMN: dict[str, str] = {
    "pv": "label_pv",
    "battery": "label_battery",
    "heat_pump": "label_heatpump",
    "ev": "label_ev",
}
DATE_COLUMN: dict[str, str] = {
    "pv": "commissioned_pv",
    "battery": "commissioned_battery",
    "heat_pump": "commissioned_heatpump",
    "ev": "commissioned_ev",
}
# Last commissioning date whose asset is still visible in the data window (window ends 2026-07).
VISIBILITY_CUTOFF = date(2025, 7, 1)


def build_labels(
    features: pl.DataFrame,
    dates: pl.DataFrame | None,
    cfg: LabelConfig,
    *,
    cutoff: date = VISIBILITY_CUTOFF,
) -> pl.DataFrame:
    """Return a frame with the ``LABELS`` schema; see the module docstring for the rules."""
    flags = features.select("gp_nr", *FLAG_COLUMN.values()).cast({"gp_nr": pl.Int64})
    if dates is not None and dates.height:
        dates = dates.select("gp_nr", *DATE_COLUMN.values()).cast({"gp_nr": pl.Int64}).unique("gp_nr")
        flags = flags.join(dates, on="gp_nr", how="left")
    else:
        flags = flags.with_columns(pl.lit(None, dtype=pl.Date).alias(c) for c in DATE_COLUMN.values())

    in_gigi = pl.any_horizontal(pl.col(c).is_not_null() for c in FLAG_COLUMN.values())
    parts = []
    for asset in ASSETS:
        flag, when = pl.col(FLAG_COLUMN[asset]), pl.col(DATE_COLUMN[asset])
        positive = (flag == 1) & (when.is_null() | (when <= pl.lit(cutoff)))
        negative = flag == 0
        parts.append(
            flags.select(
                "gp_nr",
                pl.lit(asset).alias("asset"),
                pl.when(positive).then(1).otherwise(0).alias("label"),
                pl.when(positive | negative)
                .then(pl.when(positive).then(1.0).otherwise(cfg.registry_negative_weight))
                .when(~in_gigi)
                .then(cfg.unlabeled_weight)
                .otherwise(None)
                .alias("weight"),
                pl.when(positive | negative)
                .then(pl.lit("registry"))
                .otherwise(pl.lit("unlabeled"))
                .alias("source"),
            ).filter(pl.col("weight").is_not_null())
        )
    return pl.concat(parts).sort("gp_nr", "asset").cast(dict(LABELS))
