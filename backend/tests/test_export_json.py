# tests/test_export_json.py
import json
from datetime import date, datetime, timedelta

import numpy as np
import polars as pl

from osnova.config import Config
from osnova.events.run import run_events
from osnova.export.build_json import (
    DEFAULT_REASON,
    build_buildings,
    electricity_for_day,
    events_for_day,
    write_buildings,
)
from osnova.export.curate import pick_featured, pick_others
from osnova.export.schema import BuildingsFile
from osnova.io.lastgang import feature_dataset_path
from osnova.io.store import PREDICTIONS, Store, assert_schema
from osnova.models.reasons import EVENT_LINE
from osnova.synth.generate import ORT
from tests.helpers import write_synth_by_file, write_synth_feature_dataset, write_synth_weather

ASSETS = ("pv", "battery", "heat_pump", "ev")


def _fake_predictions(gp_of: dict[int, str], truth: dict) -> pl.DataFrame:
    rng = np.random.default_rng(0)
    rows = []
    for m, gp in gp_of.items():
        t = truth["meters"][str(m)]
        rows.append(
            {
                "gp_nr": gp,
                **{
                    f"prob_{a}": float(np.clip((0.9 if t[a] else 0.1) + rng.normal(0, 0.05), 0, 1))
                    for a in ASSETS
                },
                **{f"raw_{a}": 0.5 for a in ASSETS},
                "shap_pv": json.dumps([{"feature": "midday_dip_ratio", "contribution": 0.31}]),
                "shap_battery": "[]",
                "shap_heat_pump": "[]",
                "shap_ev": "[]",
            }
        )
    preds = pl.DataFrame(rows).select(list(PREDICTIONS)).cast(dict(PREDICTIONS))
    assert_schema(preds, PREDICTIONS, "fake predictions")
    return preds


def _prepared_store(settings, synth_dir, truth) -> tuple[Store, dict[int, str], pl.DataFrame]:
    store = Store(settings)
    gp_of = write_synth_by_file(synth_dir, store, truth)
    write_synth_weather(synth_dir, store)
    write_synth_feature_dataset(store, truth)
    run_events(store, Config(), workers=1)
    preds = _fake_predictions(gp_of, truth)
    preds.write_parquet(store.predictions_path())
    return store, gp_of, preds


def test_export_end_to_end(settings, synth_dir, truth):
    store, gp_of, preds = _prepared_store(settings, synth_dir, truth)
    showcase = pl.read_parquet(store.showcase_path())
    labels = pl.read_parquet(feature_dataset_path(store))
    featured = pick_featured(labels, preds, showcase, n=3, min_types=2, min_plz=2)
    assert 1 <= len(featured) <= 3 and all(isinstance(g, int) for g in featured)
    others = pick_others(list(gp_of.values()), featured, n=5, seed=0)
    assert len(others) == 5 and not set(others) & set(featured)
    buildings = build_buildings(store, Config(), featured, others)
    path = write_buildings(store, buildings)
    parsed = BuildingsFile.model_validate_json(path.read_text()).root
    assert len(parsed) == len(featured) + 5 and parsed[0].featured is True and parsed[-1].featured is False
    b = parsed[0]
    mid = next(m for m, g in gp_of.items() if g == featured[0])
    t = truth["meters"][str(mid)]
    assert b.id == f"AG-{featured[0]}" and b.postcode == t["plz"] and b.canton == "AG"
    assert b.city == ORT[t["plz"]]  # Ort from the synth GIGI table (Table 2) for labeled buildings
    assert len(b.electricity) == 96 and b.electricity[0].timestamp.endswith(("+01:00", "+02:00"))
    assert b.profileDate == b.electricity[0].timestamp[:10]
    assert (
        b.groundTruth is not None and b.groundTruth.pv is t["pv"] and b.groundTruth.heatPump is t["heat_pump"]
    )
    assert b.history == []
    assert len({e.type for e in b.events}) >= 2 and len(b.events) <= 8
    assert all(
        e.start[:10] >= (date.fromisoformat(b.profileDate) - timedelta(days=1)).isoformat() for e in b.events
    )
    assert b.predictions.pv == int(
        round(float(preds.filter(pl.col("gp_nr") == featured[0])["prob_pv"][0]) * 100)
    )
    assert b.explanation.assets["pv"].shap[0].feature == "midday_dip_ratio"
    assert b.explanation.assets["ev"].shap == [] and b.explanation.assets["ev"].reasons
    # reasons come from models.reasons: feature-based bullets plus the band line for events on the day
    day_types = {e.type for e in b.events}
    for asset, fe_key, event_type in (("ev", "ev", "ev_charging"), ("pv", "pv", "pv_generation")):
        reasons = b.explanation.assets[fe_key].reasons
        assert 1 <= len(reasons) <= 4 and DEFAULT_REASON not in reasons
        assert (EVENT_LINE in reasons) == (event_type in day_types), (asset, reasons, day_types)
    assert any("sessions per week" in r for r in b.explanation.assets["ev"].reasons)
    unlabeled_ids = {g for m, g in gp_of.items() if not truth["meters"][str(m)]["labeled"]}
    unlabeled = [x for x in parsed if int(x.id[3:]) in unlabeled_ids]
    assert unlabeled and all(x.groundTruth is None and x.city == x.postcode for x in unlabeled)
    assert json.loads(store.featured_json().read_text()) == {"featured": featured, "others": others}


def test_city_falls_back_to_plz_without_gigi(settings, synth_dir, truth):
    settings = settings.model_copy(update={"registry_dir": settings.store_dir / "nowhere"})
    store, gp_of, _ = _prepared_store(settings, synth_dir, truth)
    labeled = [g for m, g in gp_of.items() if truth["meters"][str(m)]["labeled"]][:2]
    for b in build_buildings(store, Config(), labeled, []):
        assert b.city == b.postcode and b.canton == "AG"


def test_featured_requires_single_meter_building(settings, synth_dir, truth):
    store, gp_of, preds = _prepared_store(settings, synth_dir, truth)
    showcase = pl.read_parquet(store.showcase_path())
    labels = pl.read_parquet(feature_dataset_path(store))
    first = pick_featured(labels, preds, showcase, n=1, min_types=2, min_plz=1)
    assert len(first) == 1
    multi = labels.with_columns(
        num_mp_ids=pl.when(pl.col("gp_nr") == first[0]).then(2).otherwise(pl.col("num_mp_ids")).cast(pl.Int32)
    )
    assert first[0] not in pick_featured(multi, preds, showcase, n=3, min_types=2, min_plz=1)


def test_electricity_for_day_fills_gaps():
    rows = pl.DataFrame({"ts": [datetime(2024, 3, 31, 0, 0)], "net_kw": [1.5]}).cast(
        {"ts": pl.Datetime("ms"), "net_kw": pl.Float32}
    )
    pts = electricity_for_day(rows, date(2024, 3, 31))
    assert len(pts) == 96 and pts[0].powerKw == 1.5 and pts[1].powerKw == 0.0
    assert pts[0].timestamp == "2024-03-31T00:00:00+01:00" and pts[-1].timestamp.endswith("+02:00")


def test_events_for_day_window_and_cap():
    day = date(2024, 6, 2)
    starts = (
        [datetime(2024, 6, 1, 23, 30)]
        + [datetime(2024, 6, 2, h) for h in range(1, 11)]
        + [datetime(2024, 6, 3, 1)]
    )
    ev = pl.DataFrame(
        {
            "type": ["ev_charging"] * len(starts),
            "start": starts,
            "end": [s + timedelta(hours=1) for s in starts],
            "confidence": [0.9] * len(starts),
        }
    ).cast({"start": pl.Datetime("ms"), "end": pl.Datetime("ms")})
    out = events_for_day(ev, day)
    assert (
        len(out) == 8
        and out[0].start == "2024-06-01T23:30:00+02:00"
        and out[0].end == "2024-06-02T00:30:00+02:00"
    )
    assert all(o.start < "2024-06-03" for o in out) and [o.start for o in out] == sorted(o.start for o in out)
    early = ev.with_columns(
        start=pl.col("start") - pl.duration(hours=4), end=pl.col("end") - pl.duration(hours=4)
    )
    assert all(o.start >= "2024-06-01T18:00" for o in events_for_day(early, day))
