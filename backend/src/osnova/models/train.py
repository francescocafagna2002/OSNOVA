# src/osnova/models/train.py
"""One LightGBM per asset on the per-building feature table, with stratified out-of-fold scores,
isotonic calibration on registry rows, a rule baseline, SHAP top-6 and the PV -> battery second stage."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import polars as pl
from pydantic import BaseModel
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from osnova.config import Config
from osnova.io.store import FEATURE_KEYS, PREDICTIONS
from osnova.models.baseline import BaselineConfig, baseline_scores
from osnova.models.explain import shap_top

TRAIN_ORDER: tuple[str, ...] = ("pv", "heat_pump", "ev", "battery")
PV_PROB = "pv_prob"  # second-stage feature for the battery model
NON_FEATURE_COLUMNS = frozenset({*FEATURE_KEYS, "num_mp_ids"})  # keys + the audit column
LABEL_PREFIX = "label_"
# Existing notebooks on branch `jenia` (dataanalysis/ev_prediction): the EV model is trained on per-interval
# daily-profile features (profile_HH_MM, overall_mean, ...) that feature_dataset.parquet does not carry;
# no pv_prediction directory exists on that branch.
COMPARISON: dict[str, str] = {
    "pv": "not comparable: no pv_prediction model on branch jenia",
    "ev": "not comparable: different feature set (dataanalysis/ev_prediction uses daily-profile features)",
    "heat_pump": "no external model",
    "battery": "no external model",
}
LGB_PARAMS: dict[str, Any] = {
    "objective": "binary",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbosity": -1,
}


class TrainConfig(BaseModel):
    n_splits: int = 5
    seed: int = 42
    max_rounds: int = 1000
    early_stopping_rounds: int = 50
    fallback_rounds: int = 100  # when no cross-validation is possible (a class with < 2 rows)
    thresholds: tuple[float, ...] = (0.5, 0.8)  # FE thresholds for precision/recall
    shap_top_k: int = 6
    lgb_params: dict[str, Any] = dict(LGB_PARAMS)
    baseline: BaselineConfig = BaselineConfig()


@dataclass
class AssetModel:
    asset: str
    booster: lgb.Booster
    feature_names: list[str]
    oof: np.ndarray  # raw out-of-fold score per training row, NaN when no CV ran
    best_iterations: list[int]
    n_rounds: int
    calibrator: IsotonicRegression | None = None


@dataclass
class TrainResult:
    metrics: dict[str, dict[str, Any]]
    predictions: pl.DataFrame  # PREDICTIONS schema, one row per feature row
    models: dict[str, AssetModel] = field(default_factory=dict)
    feature_importance: pl.DataFrame | None = None


def feature_columns(features: pl.DataFrame) -> list[str]:
    """Numeric columns that are not keys, not labels and not entirely null/NaN."""
    out = []
    for name, dtype in features.schema.items():
        if name in NON_FEATURE_COLUMNS or name.startswith(LABEL_PREFIX) or not dtype.is_numeric():
            continue
        col = features[name]
        if dtype.is_float():
            col = col.fill_nan(None)
        if col.is_null().all():
            continue
        out.append(name)
    return out


def _matrix(X: pl.DataFrame, names: list[str]) -> np.ndarray:
    return X.select(names).cast({c: pl.Float64 for c in names}).to_numpy()


def _folds(y: np.ndarray, n_splits: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    smallest = int(min(np.sum(y == 1), np.sum(y == 0)))
    if smallest < 2:
        return []
    kf = StratifiedKFold(n_splits=min(n_splits, smallest), shuffle=True, random_state=seed)
    return list(kf.split(np.zeros(len(y)), y))


def train_one(asset: str, X: pl.DataFrame, y: np.ndarray, w: np.ndarray, tcfg: TrainConfig) -> AssetModel:
    names = list(X.columns)
    xn = _matrix(X, names)
    pos, neg = float(w[y == 1].sum()), float(w[y == 0].sum())
    params = {**tcfg.lgb_params, "seed": tcfg.seed, "scale_pos_weight": neg / pos if pos > 0 else 1.0}
    oof = np.full(len(y), np.nan)
    best: list[int] = []
    for tr, va in _folds(y, tcfg.n_splits, tcfg.seed):
        ds_tr = lgb.Dataset(xn[tr], y[tr], weight=w[tr], feature_name=names)
        ds_va = lgb.Dataset(xn[va], y[va], weight=w[va], feature_name=names, reference=ds_tr)
        b = lgb.train(
            params,
            ds_tr,
            num_boost_round=tcfg.max_rounds,
            valid_sets=[ds_va],
            callbacks=[lgb.early_stopping(tcfg.early_stopping_rounds, verbose=False)],
        )
        it = b.best_iteration or tcfg.max_rounds
        best.append(int(it))
        oof[va] = b.predict(xn[va], num_iteration=it)
    n_rounds = int(round(np.mean(best))) if best else tcfg.fallback_rounds
    booster = lgb.train(
        params, lgb.Dataset(xn, y, weight=w, feature_name=names), num_boost_round=max(n_rounds, 1)
    )
    return AssetModel(asset, booster, names, oof, best, n_rounds)


def _subset_metrics(y: np.ndarray, w: np.ndarray, s: np.ndarray, thresholds: tuple[float, ...]) -> dict:
    out: dict[str, Any] = {"n": int(len(y)), "n_pos": int((y == 1).sum())}
    if len(y) == 0 or len(np.unique(y)) < 2:
        out.update({"roc_auc": None, "pr_auc": None, "brier": None})
        return out
    out["roc_auc"] = float(roc_auc_score(y, s, sample_weight=w))
    out["pr_auc"] = float(average_precision_score(y, s, sample_weight=w))
    out["brier"] = float(brier_score_loss(y, s, sample_weight=w))
    for t in thresholds:
        key = f"{int(round(t * 100))}"
        pred = s >= t
        tp = float(w[pred & (y == 1)].sum())
        fp = float(w[pred & (y == 0)].sum())
        fn = float(w[~pred & (y == 1)].sum())
        out[f"precision_at_{key}"] = tp / (tp + fp) if tp + fp > 0 else None
        out[f"recall_at_{key}"] = tp / (tp + fn) if tp + fn > 0 else None
    return out


def metrics(
    y: np.ndarray,
    w: np.ndarray,
    score: np.ndarray,
    source: np.ndarray,
    thresholds: tuple[float, ...] = (0.5, 0.8),
    calibrated: np.ndarray | None = None,
) -> dict[str, dict]:
    """Metrics for all rows and for registry rows (source != "unlabeled"); NaN scores are skipped."""
    ok = np.isfinite(score)
    out = {}
    for name, mask in (("all", ok), ("registry", ok & (source != "unlabeled"))):
        m = _subset_metrics(y[mask], w[mask], score[mask], thresholds)
        if calibrated is not None and m.get("brier") is not None:
            m["brier_calibrated"] = float(brier_score_loss(y[mask], calibrated[mask], sample_weight=w[mask]))
        out[name] = m
    return out


def fit_calibrator(oof: np.ndarray, y: np.ndarray, w: np.ndarray, source: np.ndarray) -> IsotonicRegression:
    """Isotonic regression on the out-of-fold scores of registry rows (clean labels)."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    mask = np.isfinite(oof) & (source != "unlabeled")
    if mask.sum() < 2 or len(np.unique(y[mask])) < 2:
        mask = np.isfinite(oof)
    if mask.sum() < 2 or len(np.unique(y[mask])) < 2:  # no usable scores: identity on [0, 1]
        iso.fit([0.0, 1.0], [0.0, 1.0])
        return iso
    iso.fit(oof[mask], y[mask], sample_weight=w[mask])
    return iso


def _rows_for(asset: str, labels: pl.DataFrame, X_all: pl.DataFrame) -> pl.DataFrame:
    return labels.filter(pl.col("asset") == asset).join(X_all, on="gp_nr", how="inner")


def train_all(
    features: pl.DataFrame,
    labels: pl.DataFrame,
    cfg: Config,
    models_dir: Path,
    tcfg: TrainConfig | None = None,
) -> TrainResult:
    """Train pv, heat_pump, ev, battery in that order; save models and metrics; predict every feature row."""
    tcfg = tcfg or TrainConfig()
    t0 = time.perf_counter()
    models_dir.mkdir(parents=True, exist_ok=True)
    cols = feature_columns(features)
    X_all = features.select(pl.col("gp_nr").cast(pl.Int64), *cols)
    base_all = baseline_scores(features, tcfg.baseline)
    all_metrics: dict[str, dict[str, Any]] = {}
    models: dict[str, AssetModel] = {}
    importance: list[pl.DataFrame] = []
    preds: dict[str, Any] = {"gp_nr": X_all["gp_nr"]}
    for asset in TRAIN_ORDER:
        names = cols + ([PV_PROB] if asset == "battery" and PV_PROB in X_all.columns else [])
        rows = _rows_for(asset, labels, X_all)
        y = rows["label"].to_numpy().astype(int)
        w = rows["weight"].to_numpy().astype(float)
        source = rows["source"].to_numpy().astype(str)
        model = train_one(asset, rows.select(names), y, w, tcfg)
        model.calibrator = fit_calibrator(model.oof, y, w, source)
        oof_cal = np.where(np.isfinite(model.oof), model.calibrator.predict(np.nan_to_num(model.oof)), np.nan)
        base = rows.select("gp_nr").join(base_all, on="gp_nr", how="left")[f"base_{asset}"].to_numpy()
        all_metrics[asset] = {
            **metrics(y, w, model.oof, source, tcfg.thresholds, calibrated=oof_cal),
            "baseline": metrics(y, w, base.astype(float), source, tcfg.thresholds),
            "comparison": COMPARISON[asset],
            "n_rounds": model.n_rounds,
            "best_iterations": model.best_iterations,
            "feature_names": names,
        }
        raw = model.booster.predict(_matrix(X_all, names))
        prob = model.calibrator.predict(raw)
        preds[f"raw_{asset}"] = raw
        preds[f"prob_{asset}"] = prob
        preds[f"shap_{asset}"] = [json.dumps(r) for r in shap_top(model.booster, X_all, tcfg.shap_top_k)]
        if asset == "pv":  # second stage: OOF score where a PV label existed, final-model score elsewhere
            oof_frame = pl.DataFrame({"gp_nr": rows["gp_nr"], "_oof": oof_cal}).filter(
                pl.col("_oof").is_not_null()
            )
            X_all = (
                X_all.with_columns(pl.Series("_final", prob))
                .join(oof_frame, on="gp_nr", how="left")
                .with_columns(pl.coalesce("_oof", "_final").cast(pl.Float64).alias(PV_PROB))
                .drop("_oof", "_final")
            )
        importance.append(
            pl.DataFrame(
                {
                    "asset": [asset] * len(names),
                    "feature": names,
                    "gain": model.booster.feature_importance("gain").astype(float),
                    "split": model.booster.feature_importance("split").astype(int),
                }
            )
        )
        model.booster.save_model(str(models_dir / f"{asset}.txt"))
        joblib.dump(model.calibrator, models_dir / f"{asset}_calibration.joblib")
        models[asset] = model
    imp = pl.concat(importance).cast({"gain": pl.Float64, "split": pl.Int64})
    imp.write_parquet(models_dir / "feature_importance.parquet")
    (models_dir / "metrics.json").write_text(json.dumps(all_metrics, indent=2))
    predictions = pl.DataFrame(preds).select(list(PREDICTIONS)).cast(dict(PREDICTIONS))
    for m in all_metrics.values():
        m["duration_s"] = round(time.perf_counter() - t0, 1)
    return TrainResult(all_metrics, predictions, models, imp)
