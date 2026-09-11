# src/osnova/export/build_json.py
"""Join predictions, showcase day, events and the building series into buildings.json (FE contract).

Grain: one building (gp_nr) per entry, id "AG-<gp_nr>". No per-year history in this grain.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from osnova.config import ASSET_FE_KEY, ASSETS, Config
from osnova.events.showcase import last_full_day
from osnova.export.schema import (
    AssetExplanation,
    Building,
    BuildingEvent,
    BuildingExplanation,
    BuildingsFile,
    ElectricityPoint,
    GroundTruth,
    ShapFeature,
    to_fe_predictions,
)
from osnova.io.lastgang import feature_dataset_path, load_building_chunk
from osnova.io.store import Store

log = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Zurich")
INTERVAL = timedelta(minutes=15)
INTERVALS_PER_DAY = 96
MAX_EVENTS_PER_DAY = 8
EVENING_BEFORE = time(18)  # events from the evening before are folded into the showcase day by the FE
CANTON = "AG"
MODEL = "LightGBM gradient-boosted trees, one per asset"
INPUTS = ["15-minute import and export load profiles"]
ADDITIONAL_DATA = ["Open-Meteo hourly weather per postcode"]
METHOD = "SHAP"
METHOD_DESCRIPTION = "SHAP shows which features contributed most to the prediction."
DEFAULT_REASON = "Prediction based on the building's 15-minute load profile"
LABEL_COLUMNS: dict[str, str] = {
    "pv": "label_pv",
    "battery": "label_battery",
    "heat_pump": "label_heatpump",
    "ev": "label_ev",
}

ReasonsFn = Callable[[str, str, dict], list[str]]  # (gp_nr, asset, prediction row) -> reasons


def DEFAULT_REASONS(gp_nr: str, asset: str, pred_row: dict) -> list[str]:  # noqa: N802 - card name
    return [DEFAULT_REASON]


def building_id(gp_nr: str) -> str:
    return f"AG-{gp_nr}"


def _iso(ts: datetime) -> str:
    """Local naive -> ISO 8601 with the real Europe/Zurich offset of that instant."""
    return ts.replace(tzinfo=TZ).isoformat()


def _gp_str(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(gp_nr=pl.col("gp_nr").cast(pl.String).str.strip_chars())


# --------------------------------------------------------------------------- pieces


def latest_predictions(preds: pl.DataFrame) -> pl.DataFrame:
    """One row per gp_nr (the max year when a year column exists); shap_* columns default to "[]"."""
    df = _gp_str(preds)
    if "year" in df.columns:
        df = df.sort("year")
    df = df.unique("gp_nr", keep="last", maintain_order=True)
    missing = [f"shap_{a}" for a in ASSETS if f"shap_{a}" not in df.columns]
    return df.with_columns([pl.lit("[]").alias(c) for c in missing])


def electricity_for_day(day_rows: pl.DataFrame, day: date) -> list[ElectricityPoint]:
    """96 net-power points of `day`; missing intervals are 0.0."""
    values = dict(zip(day_rows["ts"].to_list(), day_rows["net_kw"].to_list(), strict=True))
    start = datetime.combine(day, time())
    out = []
    for i in range(INTERVALS_PER_DAY):
        t = start + i * INTERVAL
        v = values.get(t)
        out.append(ElectricityPoint(timestamp=_iso(t), powerKw=round(float(v), 3) if v is not None else 0.0))
    return out


def events_for_day(
    events: pl.DataFrame, day: date, max_events: int = MAX_EVENTS_PER_DAY
) -> list[BuildingEvent]:
    """Events touching `day`, including the evening before (EV sessions cross midnight)."""
    lo = datetime.combine(day - timedelta(days=1), EVENING_BEFORE)
    mid = datetime.combine(day, time())
    hi = mid + timedelta(days=1)
    sel = (
        events.filter((pl.col("start") >= lo) & (pl.col("end") > mid) & (pl.col("start") < hi))
        .sort("start")
        .head(max_events)
    )
    return [
        BuildingEvent(
            type=r["type"],
            start=_iso(r["start"]),
            end=_iso(r["end"]),
            confidence=round(float(r["confidence"]), 3) if r.get("confidence") is not None else None,
        )
        for r in sel.iter_rows(named=True)
    ]


def ground_truth(label_row: dict | None) -> GroundTruth | None:
    """label_* 1/0/null -> True/False/None; None when the building has no label at all."""
    if label_row is None:
        return None
    values = {ASSET_FE_KEY[a]: label_row.get(col) for a, col in LABEL_COLUMNS.items()}
    if all(v is None for v in values.values()):
        return None
    return GroundTruth(**{k: (None if v is None else bool(v)) for k, v in values.items()})


def build_building(
    gp_nr: str,
    *,
    plz: str,
    city: str,
    pred_row: dict,
    day: date,
    day_rows: pl.DataFrame,
    events: pl.DataFrame,
    label_row: dict | None,
    featured: bool,
    reasons_fn: ReasonsFn = DEFAULT_REASONS,
) -> Building:
    probs = {a: float(pred_row.get(f"prob_{a}") or 0.0) for a in ASSETS}
    assets = {
        ASSET_FE_KEY[a]: AssetExplanation(
            reasons=reasons_fn(gp_nr, a, pred_row),
            shap=[ShapFeature(**s) for s in json.loads(pred_row.get(f"shap_{a}") or "[]")],
        )
        for a in ASSETS
    }
    return Building(
        id=building_id(gp_nr),
        postcode=plz,
        city=city,
        canton=CANTON,
        predictions=to_fe_predictions(probs),
        electricity=electricity_for_day(day_rows, day),
        events=events_for_day(events, day),
        explanation=BuildingExplanation(
            model=MODEL,
            inputs=INPUTS,
            additionalData=ADDITIONAL_DATA,
            method=METHOD,
            methodDescription=METHOD_DESCRIPTION,
            assets=assets,
        ),
        featured=featured,
        profileDate=day.isoformat(),
        groundTruth=ground_truth(label_row),
        history=[],
    )


# --------------------------------------------------------------------------- inputs


@dataclass
class ExportInputs:
    predictions: pl.DataFrame  # one row per gp_nr
    showcase: pl.DataFrame
    events: pl.DataFrame
    labels: pl.DataFrame | None  # feature_dataset.parquet: gp_nr, plz, label_*
    ort: dict[str, str]  # gp_nr -> Ort from the registry (GIGI), when present


def load_labels(store: Store) -> pl.DataFrame | None:
    path = feature_dataset_path(store)
    if not path.exists():
        return None
    df = pl.read_parquet(path)
    cols = ["gp_nr", *[c for c in ("plz", *LABEL_COLUMNS.values()) if c in df.columns]]
    return _gp_str(df.select(cols)).unique("gp_nr", keep="first")


def load_ort(store: Store) -> dict[str, str]:
    path = store.registry_path()
    if not path.exists():
        return {}
    reg = pl.read_parquet(path)
    if "ort" not in reg.columns:
        return {}
    reg = _gp_str(reg.select("gp_nr", "ort")).drop_nulls().filter(pl.col("ort").str.len_chars() > 0)
    return dict(reg.unique("gp_nr", keep="first").iter_rows())


def load_inputs(store: Store) -> ExportInputs:
    return ExportInputs(
        predictions=latest_predictions(pl.read_parquet(store.predictions_path())),
        showcase=_gp_str(pl.read_parquet(store.showcase_path())),
        events=_gp_str(pl.read_parquet(store.events_path())),
        labels=load_labels(store),
        ort=load_ort(store),
    )


# --------------------------------------------------------------------------- build + write


def build_buildings(
    store: Store,
    cfg: Config,
    featured_ids: list[str],
    other_ids: list[str],
    reasons_fn: ReasonsFn = DEFAULT_REASONS,
) -> list[Building]:
    """Featured first, then the others. Buildings without predictions or series are skipped (logged)."""
    inputs = load_inputs(store)
    wanted = [(str(g), True) for g in featured_ids] + [(str(g), False) for g in other_ids]
    series_by_gp = load_building_chunk(store, [g for g, _ in wanted])
    preds = {r["gp_nr"]: r for r in inputs.predictions.iter_rows(named=True)}
    showcase = {r["gp_nr"]: r for r in inputs.showcase.iter_rows(named=True)}
    labels = {r["gp_nr"]: r for r in inputs.labels.iter_rows(named=True)} if inputs.labels is not None else {}
    events_by_gp = inputs.events.partition_by("gp_nr", as_dict=True)
    out: list[Building] = []
    for gp, featured in wanted:
        series = series_by_gp[gp]
        pred_row = preds.get(gp)
        if pred_row is None or series.height == 0:
            log.warning("skip %s: %s", gp, "no predictions" if pred_row is None else "no series")
            continue
        sc = showcase.get(gp)
        day = (
            sc["showcase_date"]
            if sc is not None and sc["showcase_date"] is not None
            else last_full_day(series)
        )
        label_row = labels.get(gp)
        plz = series["plz"].drop_nulls().first() or (label_row or {}).get("plz") or ""
        out.append(
            build_building(
                gp,
                plz=str(plz),
                city=inputs.ort.get(gp) or str(plz),
                pred_row=pred_row,
                day=day,
                day_rows=series.filter(pl.col("ts").dt.date() == day),
                events=events_by_gp.get((gp,), inputs.events.head(0)),
                label_row=label_row,
                featured=featured,
                reasons_fn=reasons_fn,
            )
        )
    return out


def write_featured(store: Store, featured: list[str], others: list[str]) -> Path:
    path = store.featured_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"featured": list(featured), "others": list(others)}, indent=1))
    return path


def load_featured(store: Store) -> tuple[list[str], list[str]] | None:
    path = store.featured_json()
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return [str(g) for g in data.get("featured", [])], [str(g) for g in data.get("others", [])]


def write_buildings(store: Store, buildings: list[Building]) -> Path:
    """Validate with the FE schema, featured first, and write buildings.json + featured.json."""
    ordered = [b for b in buildings if b.featured] + [b for b in buildings if not b.featured]
    payload = BuildingsFile(ordered)
    path = store.buildings_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload.model_dump_json(exclude_none=False))
    write_featured(
        store, [b.id[3:] for b in ordered if b.featured], [b.id[3:] for b in ordered if not b.featured]
    )
    return path
