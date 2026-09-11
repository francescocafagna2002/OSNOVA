# src/osnova/models/explain.py
"""SHAP top-k contributions per row, scaled to roughly -1..1 for the FE."""

from __future__ import annotations

import math
import warnings

import lightgbm as lgb
import numpy as np
import polars as pl
import shap

from osnova.models.reasons import FEATURE_LABELS

SHAP_SCALE = 2.0  # contribution = tanh(shap_value / SHAP_SCALE); shap values are in log-odds


def feature_label(name: str) -> str:
    return FEATURE_LABELS.get(name, name.replace("_", " ").capitalize())


def shap_values(booster: lgb.Booster, X: pl.DataFrame) -> np.ndarray:
    """(n_rows, n_features) log-odds contributions, columns in the booster's feature order."""
    names = booster.feature_name()
    xn = X.select(names).cast({c: pl.Float64 for c in names}).to_numpy()
    with warnings.catch_warnings():  # shap warns that LightGBM binary output "has changed to a list"
        warnings.filterwarnings("ignore", message=".*LightGBM binary classifier.*", category=UserWarning)
        values = shap.TreeExplainer(booster).shap_values(xn)
    if isinstance(values, list):  # older shap: [class 0, class 1]
        values = values[-1]
    values = np.asarray(values)
    if values.ndim == 3:  # (n, features, classes)
        values = values[:, :, -1]
    return values


def shap_top(booster: lgb.Booster, X: pl.DataFrame, k: int = 6) -> list[list[dict]]:
    """Per row: the k largest |contributions| as {"feature": label, "contribution": tanh(v/2)},
    sorted by |contribution| descending."""
    names = booster.feature_name()
    values = shap_values(booster, X)
    out: list[list[dict]] = []
    for row in values:
        order = np.argsort(-np.abs(row))[:k]
        out.append(
            [
                {"feature": feature_label(names[i]), "contribution": round(math.tanh(row[i] / SHAP_SCALE), 3)}
                for i in order
            ]
        )
    return out
