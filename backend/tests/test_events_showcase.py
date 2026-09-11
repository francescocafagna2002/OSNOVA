# tests/test_events_showcase.py
import json
from datetime import date, datetime, timedelta

import polars as pl

from osnova.config import EVENT_TYPES, Config, EventConfig
from osnova.events.high_load import detect_high_load
from osnova.events.run import run_events
from osnova.events.showcase import pick_showcase_day
from osnova.io.store import EVENTS, SHOWCASE, Store, assert_schema
from tests.helpers import write_synth_by_file, write_synth_weather


def test_pick_showcase_prefers_distinct_types():
    ev = pl.DataFrame(
        {
            "type": ["ev_charging", "pv_generation", "ev_charging", "high_consumption", "ev_charging"],
            "start": [
                datetime(2024, 6, 1, 22),
                datetime(2024, 6, 1, 10),
                datetime(2024, 6, 2, 22),
                datetime(2024, 6, 2, 18),
                datetime(2024, 6, 3, 22),
            ],
            "confidence": [0.9, 0.8, 0.95, 0.5, 0.9],
        }
    )
    assert pick_showcase_day(ev, EventConfig()) == (date(2024, 6, 1), 2)  # 6/2's high_consumption < 0.6
    assert pick_showcase_day(ev.head(0), EventConfig()) is None


def _day(load: list[float]) -> pl.DataFrame:
    ts = [datetime(2024, 3, 5) + timedelta(minutes=15 * i) for i in range(96)]
    return pl.DataFrame({"ts": ts, "import_kw": load}).cast(
        {"ts": pl.Datetime("ms"), "import_kw": pl.Float32}
    )


def test_high_load_takes_longest_unclaimed_run():
    load = [0.4] * 96
    load[72:80] = [3.0] * 8  # 18:00-20:00, the day's clear peak
    load[30:33] = [2.0] * 3  # short bump, below min intervals
    cfg = EventConfig()
    out = detect_high_load(
        _day(load), pl.DataFrame(schema={"start": pl.Datetime("ms"), "end": pl.Datetime("ms")}), cfg
    )
    assert out.height == 1
    assert out["start"][0] == datetime(2024, 3, 5, 18) and out["end"][0] == datetime(2024, 3, 5, 20)
    assert abs(out["peak_kw"][0] - 3.0) < 1e-6 and abs(out["energy_kwh"][0] - 6.0) < 1e-6
    claimed = pl.DataFrame({"start": [datetime(2024, 3, 5, 19)], "end": [datetime(2024, 3, 5, 21)]}).cast(
        {"start": pl.Datetime("ms"), "end": pl.Datetime("ms")}
    )
    assert detect_high_load(_day(load), claimed, cfg).height == 0


def test_run_events_on_synth(settings, synth_dir, truth):
    store = Store(settings)
    gp_of = write_synth_by_file(synth_dir, store, truth)
    write_synth_weather(synth_dir, store)
    events, showcase = run_events(store, Config(), workers=2)
    assert_schema(events, EVENTS, "events")
    assert_schema(showcase, SHOWCASE, "showcase")
    assert showcase.height == len(gp_of) and showcase["gp_nr"].n_unique() == len(gp_of)
    assert set(events["type"].unique().to_list()) <= set(EVENT_TYPES)
    ev_gps = {gp_of[int(m)] for m, t in truth["meters"].items() if t["ev"] and t["commissioned_on"] is None}
    ev_events = events.filter(pl.col("type") == "ev_charging")
    per_gp = ev_events.group_by("gp_nr").len()
    assert set(per_gp.filter(pl.col("len") > 100)["gp_nr"].to_list()) >= ev_gps
    assert ev_events["peak_kw"].min() > 2.0  # plateau, not residual noise
    pv_gps = {gp_of[int(m)] for m, t in truth["meters"].items() if t["pv"] and t["commissioned_on"] is None}
    assert set(events.filter(pl.col("type") == "pv_generation")["gp_nr"].unique().to_list()) >= pv_gps
    assert showcase.filter(pl.col("n_event_types") >= 2).height > 0
    assert (showcase["showcase_date"] >= date(2023, 1, 1)).all()
    assert pl.read_parquet(store.events_path()).height == events.height
    assert pl.read_parquet(store.showcase_path()).height == showcase.height
    manifest = json.loads((store.root / "_manifest_events.json").read_text())
    assert manifest["n_buildings"] == len(gp_of) and manifest["n_events"] == events.height
