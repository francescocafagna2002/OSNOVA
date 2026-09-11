# src/osnova/models/reasons.py
"""Human labels for feature names and the plain-language `reasons` bullets for the FE.

Everything a copy-editor might touch lives in this file. Wording never states an asset as fact:
"consistent with", "no sign of". Templates are skipped when a value is missing or NaN.
"""

from __future__ import annotations

import math
from string import Formatter

import polars as pl

from osnova.config import ASSETS

# One label per column of feature_dataset.parquet (feature_pipeline FINAL_COLUMNS) plus the
# second-stage `pv_prob`. The `-5` spellings are aliases for the same cold bins.
FEATURE_LABELS: dict[str, str] = {
    "num_mp_ids": "Meters in the building",
    "n_valid_days": "Days with valid data",
    "pv_presence": "PV presence placeholder",
    "pv_prob": "Estimated PV probability",
    # battery
    "near_zero_interval_ratio": "Share of intervals with net load near zero",
    "number_of_near_zero_blocks": "Number of near-zero load blocks",
    "daytime_near_zero_ratio": "Share of midday intervals near zero",
    "evening_near_zero_ratio": "Share of evening intervals near zero",
    "consumption_per_unit_solar_radiation": "Net load per unit of solar radiation",
    # pv
    "daytime_mean_power": "Mean midday net load",
    "morning_mean_power": "Mean morning net load",
    "evening_mean_power": "Mean evening net load",
    "negative_consumption_ratio": "Share of intervals exporting to the grid",
    "negative_daytime_consumption_ratio": "Share of midday intervals exporting",
    "total_export_kwh": "Total energy exported",
    "days_with_export_ratio": "Share of days with export",
    "summer_midday_mean": "Summer midday net load",
    "winter_midday_mean": "Winter midday net load",
    "summer_vs_winter_midday_diff": "Winter minus summer midday load",
    "correlation_solar_radiation_consumption": "Correlation of net load with solar radiation",
    "correlation_sunshine_duration_consumption": "Correlation of net load with sunshine hours",
    "sunny_day_midday_mean": "Midday net load on sunny days",
    "cloudy_day_midday_mean": "Midday net load on cloudy days",
    # ev
    "count_events_above_3kw": "Load runs above 3 kW",
    "count_events_above_5kw": "Load runs above 5 kW",
    "count_events_above_7kw": "Load runs above 7 kW",
    "count_events_above_11kw": "Load runs above 11 kW",
    "median_consumption": "Median load",
    "p95_consumption": "95th percentile load",
    "p99_consumption": "99th percentile load",
    "max_consumption": "Peak load",
    "max_positive_ramp": "Largest load step up",
    "max_negative_ramp": "Largest load step down",
    "p95_positive_ramp": "95th percentile step up",
    "p99_positive_ramp": "99th percentile step up",
    "p95_negative_ramp": "95th percentile step down",
    "p99_negative_ramp": "99th percentile step down",
    "session_mean": "Mean power of high-load sessions",
    "session_median": "Median power of high-load sessions",
    "session_std": "Spread of session power",
    "session_variance": "Variance of session power",
    "session_cv": "Session power variability",
    "morning_start_ratio": "Sessions starting in the morning",
    "midday_start_ratio": "Sessions starting at midday",
    "evening_start_ratio": "Sessions starting in the evening",
    "night_start_ratio": "Sessions starting at night",
    "morning_finish_ratio": "Sessions ending in the morning",
    "midday_finish_ratio": "Sessions ending at midday",
    "evening_finish_ratio": "Sessions ending in the evening",
    "night_finish_ratio": "Sessions ending at night",
    "morning_high_load_ratio": "High load in the morning",
    "midday_high_load_ratio": "High load at midday",
    "evening_high_load_ratio": "High load in the evening",
    "night_high_load_ratio": "High load at night",
    "sessions_per_week": "Charging-like sessions per week",
    # heat pump
    "correlation_outside_temperature_consumption": "Correlation of load with outdoor temperature",
    "mean_consumption_T_below_minus5": "Mean load below -5 °C",
    "mean_consumption_T_minus5_to_0": "Mean load between -5 and 0 °C",
    "mean_consumption_T_0_to_5": "Mean load between 0 and 5 °C",
    "mean_consumption_T_5_to_10": "Mean load between 5 and 10 °C",
    "mean_consumption_T_10_to_15": "Mean load between 10 and 15 °C",
    "mean_consumption_T_above_15": "Mean load above 15 °C",
    "mean_consumption_T_below_-5": "Mean load below -5 °C",
    "mean_consumption_T_-5_to_0": "Mean load between -5 and 0 °C",
    "winter_night_mean_consumption": "Winter night load",
    "summer_night_mean_consumption": "Summer night load",
}

# Values derived from the feature dict before formatting (name -> (inputs, function)).
DERIVED: dict[str, tuple[tuple[str, ...], object]] = {
    "evening_night_start_ratio": (("evening_start_ratio", "night_start_ratio"), lambda e, n: e + n),
    "winter_summer_night_ratio": (
        ("winter_night_mean_consumption", "summer_night_mean_consumption"),
        lambda w, s: w / s if s > 0 else math.nan,
    ),
    "cold_warm_load_ratio": (
        ("mean_consumption_T_below_minus5", "mean_consumption_T_above_15"),
        lambda c, w: c / w if w > 0 else math.nan,
    ),
}

TEMPLATES: dict[str, dict[str, list[str]]] = {
    "pv": {
        "likely": [
            "{days_with_export_ratio:.0%} of days feed power back to the grid",
            "Net load correlates with solar radiation (r = {correlation_solar_radiation_consumption:.2f})",
            "Midday net load is {sunny_day_midday_mean:.1f} kW on sunny days vs "
            "{cloudy_day_midday_mean:.1f} kW on cloudy days",
        ],
        "unlikely": [
            "Only {days_with_export_ratio:.0%} of days show any export to the grid",
            "Midday net load does not follow solar radiation "
            "(r = {correlation_solar_radiation_consumption:.2f})",
            "No midday reduction in net load",
        ],
    },
    "battery": {
        "likely": [
            "Net load sits near zero in {near_zero_interval_ratio:.0%} of intervals",
            "{evening_near_zero_ratio:.0%} of evening intervals are near zero, consistent with discharging",
            "Estimated PV probability {pv_prob:.0%}, a battery usually pairs with PV",
        ],
        "unlikely": [
            "Net load sits near zero in only {near_zero_interval_ratio:.0%} of intervals",
            "Midday surplus is exported rather than stored",
        ],
    },
    "heat_pump": {
        "likely": [
            "Load below -5 °C is {cold_warm_load_ratio:.1f}× the load above 15 °C",
            "Winter nights use {winter_summer_night_ratio:.1f}× the power of summer nights",
            "Load rises as it gets colder (r = {correlation_outside_temperature_consumption:.2f})",
        ],
        "unlikely": [
            "Load barely changes with outdoor temperature "
            "(r = {correlation_outside_temperature_consumption:.2f})",
            "Winter and summer night loads are similar ({winter_summer_night_ratio:.1f}×)",
        ],
    },
    "ev": {
        "likely": [
            "{sessions_per_week:.1f} charging-like sessions per week, plateau ≈ {session_median:.1f} kW",
            "{evening_night_start_ratio:.0%} of sessions start in the evening or at night",
            "{count_events_above_7kw:.0f} load runs above 7 kW",
        ],
        "unlikely": [
            "Only {sessions_per_week:.1f} high-load sessions per week",
            "Peak load stays below {p99_consumption:.1f} kW",
            "No repeated high-power plateaus",
        ],
    },
}
ASSET_NAME = {"pv": "a PV system", "battery": "a battery", "heat_pump": "a heat pump", "ev": "an EV charger"}
FALLBACK = {
    "likely": "Consumption pattern is consistent with {asset}",
    "unlikely": "No sign of {asset} in the consumption pattern",
}
EVENT_TYPE = {
    "pv": "pv_generation",
    "battery": "battery_cycle",
    "heat_pump": "heat_pump_heating",
    "ev": "ev_charging",
}
EVENT_LINE = "Visible on the selected day as a highlighted band"
MAX_REASONS = 3
LIKELY_THRESHOLD = 0.5


def _usable(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _values(feats: dict[str, object]) -> dict[str, float]:
    out = {k: float(v) for k, v in feats.items() if _usable(v)}
    for name, (inputs, fn) in DERIVED.items():
        if all(i in out for i in inputs):
            val = fn(*(out[i] for i in inputs))
            if _usable(val):
                out[name] = val
    return out


def _fields(template: str) -> list[str]:
    return [f for _, f, _, _ in Formatter().parse(template) if f]


def reasons_for(
    asset: str, feats: dict[str, object], prob: float, events_day: pl.DataFrame | None
) -> list[str]:
    """2-3 bullets for one asset from its features and probability; plus one line when the showcase
    day carries the asset's event type. Templates whose values are missing or NaN are skipped."""
    if asset not in ASSETS:
        raise ValueError(f"unknown asset {asset!r}")
    mode = "likely" if prob >= LIKELY_THRESHOLD else "unlikely"
    values = _values(feats)
    out: list[str] = []
    for template in TEMPLATES[asset][mode]:
        if all(f in values for f in _fields(template)):
            out.append(template.format(**values))
        if len(out) == MAX_REASONS:
            break
    if not out:
        out.append(FALLBACK[mode].format(asset=ASSET_NAME[asset]))
    if events_day is not None and "type" in events_day.columns:
        if (events_day["type"] == EVENT_TYPE[asset]).any():
            out.append(EVENT_LINE)
    return out
