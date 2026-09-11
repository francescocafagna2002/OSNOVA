# src/osnova/export/curate.py
"""Pick the featured buildings (labeled, confident, agreeing, eventful, spread over PLZ) and the others."""

from __future__ import annotations

import logging

import numpy as np
import polars as pl

from osnova.config import ASSETS
from osnova.export.build_json import LABEL_COLUMNS, _gp_str, latest_predictions

log = logging.getLogger(__name__)

PROB_AGREE_MIN = 0.8  # an asset "agrees" when prob >= this and the ground truth is true
MIN_AGREEING_ASSETS = 2


def _round_robin(cand: pl.DataFrame, n: int) -> list[str]:
    """Take the best candidate of each PLZ in turn (PLZ ordered by their best candidate) until n."""
    queues: dict[str, list[str]] = {}
    for r in cand.iter_rows(named=True):
        queues.setdefault(str(r.get("plz") or ""), []).append(r["gp_nr"])
    out: list[str] = []
    while len(out) < n and any(queues.values()):
        for plz in list(queues):
            if queues[plz] and len(out) < n:
                out.append(queues[plz].pop(0))
    return out


def pick_featured(
    labels: pl.DataFrame,
    latest_preds: pl.DataFrame,
    showcase: pl.DataFrame,
    n: int = 10,
    min_types: int = 3,
    min_plz: int = 5,
) -> list[str]:
    """labels: gp_nr, plz?, label_* (1/0/null). Returns gp_nr strings, best first."""
    if labels.height == 0:
        return []
    lab = _gp_str(labels)
    if "plz" not in lab.columns:
        lab = lab.with_columns(plz=pl.lit(""))
    label_cols = [c for c in LABEL_COLUMNS.values() if c in lab.columns]
    preds = latest_predictions(latest_preds)
    sc = _gp_str(showcase).select("gp_nr", "n_event_types")
    agree = [
        ((pl.col(f"prob_{a}") >= PROB_AGREE_MIN) & (pl.col(col) == 1)).fill_null(False).cast(pl.Int32)
        for a, col in LABEL_COLUMNS.items()
        if col in label_cols
    ]
    cand = (
        lab.join(preds, on="gp_nr", how="inner")
        .join(sc, on="gp_nr", how="inner")
        .with_columns(
            labeled=pl.any_horizontal([pl.col(c).is_not_null() for c in label_cols])
            if label_cols
            else pl.lit(False),
            agreement=pl.sum_horizontal(agree) if agree else pl.lit(0),
            prob_sum=pl.sum_horizontal([pl.col(f"prob_{a}") for a in ASSETS]),
        )
        .filter(
            pl.col("labeled")
            & (pl.col("n_event_types") >= min_types)
            & (pl.col("agreement") >= MIN_AGREEING_ASSETS)
        )
        .sort(["agreement", "prob_sum"], descending=[True, True])
    )
    picked = _round_robin(cand, n)
    n_plz = cand.filter(pl.col("gp_nr").is_in(picked))["plz"].n_unique()
    if len(picked) < n or n_plz < min_plz:
        log.warning("featured: %d of %d wanted, over %d PLZ (wanted >= %d)", len(picked), n, n_plz, min_plz)
    return picked


def pick_others(all_ids: list[str], exclude: list[str], n: int, seed: int = 0) -> list[str]:
    """Seeded random sample of the remaining buildings, sorted for stable output."""
    pool = sorted(set(map(str, all_ids)) - set(map(str, exclude)))
    rng = np.random.default_rng(seed)
    k = min(n, len(pool))
    return sorted(rng.choice(pool, size=k, replace=False).tolist()) if k else []
