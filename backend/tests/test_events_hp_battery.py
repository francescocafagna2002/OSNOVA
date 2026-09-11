# tests/test_events_hp_battery.py
import polars as pl

from osnova.config import EventConfig
from osnova.events.battery_cycles import detect_battery_cycles
from osnova.events.hp_heating import detect_hp_heating
from tests.helpers import meter_year, pick


def test_hp_heating_events_in_winter(synth_dir, truth):
    hp = detect_hp_heating(meter_year(synth_dir, pick(truth, heat_pump=True), 2024).df, EventConfig())
    no = detect_hp_heating(
        meter_year(synth_dir, pick(truth, heat_pump=False, ev=False), 2024).df, EventConfig()
    )
    assert hp.height >= 40 and (hp["start"].dt.month().is_in([1, 2, 12])).all()
    assert hp["confidence"].mean() > 0.5 and no.height < 10
    assert hp["start"].dt.date().n_unique() == hp.height  # one event per day


def test_battery_cycles(synth_dir, truth):
    bat = detect_battery_cycles(
        meter_year(synth_dir, pick(truth, pv=True, battery=True), 2024).df, EventConfig()
    )
    pv_only = detect_battery_cycles(
        meter_year(synth_dir, pick(truth, pv=True, battery=False), 2024).df, EventConfig()
    )
    assert bat.height >= 30 and bat.height > 3 * max(pv_only.height, 1)
    assert (bat["confidence"] >= 0.6).all()
    assert (bat["end"] > bat["start"]).all()


def test_detectors_handle_empty_and_weatherless_frames(synth_dir, truth):
    df = meter_year(synth_dir, pick(truth, heat_pump=True), 2024).df
    assert detect_hp_heating(df.head(0), EventConfig()).height == 0
    no_weather = df.with_columns(temperature_2m=pl.lit(None, pl.Float32))
    out = detect_hp_heating(no_weather, EventConfig())
    assert out.height > 0 and (out["confidence"] == 0.5).all()
    assert (
        detect_battery_cycles(df.with_columns(is_sunny_day=pl.lit(None, pl.Boolean)), EventConfig()).height
        == 0
    )
