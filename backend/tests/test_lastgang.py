# tests/test_lastgang.py
import polars as pl

from osnova.io.lastgang import BUILDING_SERIES, by_file_dir, load_building_series
from osnova.io.store import Store
from osnova.synth.loader import load_synth_meter
from tests.helpers import pick, write_synth_by_file


def test_load_building_series_matches_synth(settings, synth_dir, truth):
    store = Store(settings)
    gp_of = write_synth_by_file(synth_dir, store, truth)
    mid = pick(truth, pv=True)
    out = load_building_series(store, gp_of[mid])
    assert out.schema == BUILDING_SERIES
    assert out["ts"].is_sorted() and out["ts"].n_unique() == out.height
    assert out.height == 2 * 366 * 96 - 96  # 2023 + 2024 (leap), synth grid
    ref = load_synth_meter(synth_dir, mid, 2024).sort("ts")
    got = out.filter(pl.col("ts").dt.year() == 2024)
    assert got.height == ref.height
    assert (got["net_kw"] - ref["net_kw"]).abs().max() < 1e-3
    assert (got["import_kw"] - ref["import_kw"]).abs().max() < 1e-3
    assert (got["export_kw"] - ref["export_kw"]).abs().max() < 1e-3
    assert got["export_kw"].max() > 1.0 and got["import_kw"].min() >= 0
    assert (out["quality"] == "ok").all() and (out["plz"] == truth["meters"][str(mid)]["plz"]).all()


def test_load_building_series_marks_missing_and_unknown(settings, synth_dir, truth):
    store = Store(settings)
    gp_of = write_synth_by_file(synth_dir, store, truth, years=(2024,))
    gp = gp_of[pick(truth, ev=False)]
    # null power in one file -> quality "missing", net 0
    f = sorted(by_file_dir(store).glob("*.parquet"))[0]
    df = pl.read_parquet(f)
    df.with_columns(
        power_kw=pl.when(pl.col("gp_nr") == gp).then(None).otherwise(pl.col("power_kw"))
    ).write_parquet(f)
    out = load_building_series(store, gp)
    assert (out["quality"] == "missing").sum() > 0 and out.filter(pl.col("quality") == "missing")[
        "net_kw"
    ].null_count() == 0
    empty = load_building_series(store, "000000")
    assert empty.height == 0 and empty.schema == BUILDING_SERIES
