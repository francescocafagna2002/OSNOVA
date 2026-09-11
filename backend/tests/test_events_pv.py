# tests/test_events_pv.py
import polars as pl

from osnova.config import EventConfig, FeatureConfig
from osnova.events.pv_windows import detect_pv_windows
from tests.helpers import meter_year, pick


def test_pv_windows_on_exporting_meter(synth_dir, truth):
    my = meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024)
    out = detect_pv_windows(my.df, night_baseline_kw=0.4, cfg=EventConfig())
    july = out.filter(pl.col("start").dt.month() == 7)
    assert july.height >= 25
    assert (july["start"].dt.hour().median() <= 9) and (july["end"].dt.hour().median() >= 16)
    assert (july["confidence"] >= 0.7).all() and july["peak_kw"].mean() > 1.0


def test_no_windows_without_pv(synth_dir, truth):
    my = meter_year(synth_dir, pick(truth, pv=False), 2024, FeatureConfig())
    out = detect_pv_windows(my.df, night_baseline_kw=0.4, cfg=EventConfig())
    assert out.height < 20  # a few sunny-day false positives are acceptable
