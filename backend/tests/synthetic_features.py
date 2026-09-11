# tests/synthetic_features.py
"""A synthetic feature_dataset.parquet-shaped table with the team's column names and injected assets."""

from __future__ import annotations

from datetime import date

import numpy as np
import polars as pl

ASSETS = ("pv", "battery", "heat_pump", "ev")

# FINAL_COLUMNS of feature_pipeline/pipeline.py (branch feat/backend-feature-pipeline) plus n_valid_days.
FEATURE_DATASET_COLUMNS = [
    "gp_nr",
    "plz",
    "num_mp_ids",
    "n_valid_days",
    "near_zero_interval_ratio",
    "number_of_near_zero_blocks",
    "daytime_near_zero_ratio",
    "evening_near_zero_ratio",
    "consumption_per_unit_solar_radiation",
    "daytime_mean_power",
    "morning_mean_power",
    "evening_mean_power",
    "negative_consumption_ratio",
    "negative_daytime_consumption_ratio",
    "total_export_kwh",
    "days_with_export_ratio",
    "summer_midday_mean",
    "winter_midday_mean",
    "summer_vs_winter_midday_diff",
    "correlation_solar_radiation_consumption",
    "correlation_sunshine_duration_consumption",
    "sunny_day_midday_mean",
    "cloudy_day_midday_mean",
    "count_events_above_3kw",
    "count_events_above_5kw",
    "count_events_above_7kw",
    "count_events_above_11kw",
    "median_consumption",
    "p95_consumption",
    "p99_consumption",
    "max_consumption",
    "max_positive_ramp",
    "max_negative_ramp",
    "p95_positive_ramp",
    "p99_positive_ramp",
    "p95_negative_ramp",
    "p99_negative_ramp",
    "session_mean",
    "session_median",
    "session_std",
    "session_variance",
    "session_cv",
    "morning_start_ratio",
    "midday_start_ratio",
    "evening_start_ratio",
    "night_start_ratio",
    "morning_finish_ratio",
    "midday_finish_ratio",
    "evening_finish_ratio",
    "night_finish_ratio",
    "morning_high_load_ratio",
    "midday_high_load_ratio",
    "evening_high_load_ratio",
    "night_high_load_ratio",
    "sessions_per_week",
    "correlation_outside_temperature_consumption",
    "mean_consumption_T_below_minus5",
    "mean_consumption_T_minus5_to_0",
    "mean_consumption_T_0_to_5",
    "mean_consumption_T_5_to_10",
    "mean_consumption_T_10_to_15",
    "mean_consumption_T_above_15",
    "winter_night_mean_consumption",
    "summer_night_mean_consumption",
    "label_pv",
    "label_ev",
    "label_heatpump",
    "label_battery",
]
LABEL_COLUMN = {"pv": "label_pv", "battery": "label_battery", "heat_pump": "label_heatpump", "ev": "label_ev"}
DATE_COLUMN = {
    "pv": "commissioned_pv",
    "battery": "commissioned_battery",
    "heat_pump": "commissioned_heatpump",
    "ev": "commissioned_ev",
}


def synthetic_table(
    n: int = 300, seed: int = 0, *, unlabeled_every: int = 3, late_every: int = 25
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, np.ndarray]]:
    """Return (features, dates, truth). Every ``unlabeled_every``-th building is not in GIGI (all flags
    null); every ``late_every``-th positive PV is commissioned after the cutoff."""
    rng = np.random.default_rng(seed)
    truth = {a: rng.random(n) < 0.3 for a in ASSETS}
    truth["battery"] &= truth["pv"]  # a battery without PV is rare
    pv, bat, hp, ev = truth["pv"], truth["battery"], truth["heat_pump"], truth["ev"]
    z = lambda s=1.0: rng.normal(0, s, n)  # noqa: E731
    cols: dict[str, np.ndarray] = {
        "near_zero_interval_ratio": np.where(bat, 0.35, 0.05) + rng.normal(0, 0.03, n),
        "number_of_near_zero_blocks": np.where(bat, 600, 80) + rng.normal(0, 30, n),
        "daytime_near_zero_ratio": np.where(bat, 0.5, 0.08) + rng.normal(0, 0.04, n),
        "evening_near_zero_ratio": np.where(bat, 0.4, 0.03) + rng.normal(0, 0.04, n),
        "consumption_per_unit_solar_radiation": np.where(pv, -0.004, 0.001) + rng.normal(0, 0.0005, n),
        "daytime_mean_power": np.where(pv, -1.0, 0.6) + z(0.2),
        "morning_mean_power": 0.5 + z(0.1),
        "evening_mean_power": 1.0 + np.where(bat, -0.5, 0.0) + z(0.2),
        "negative_consumption_ratio": np.where(pv, 0.25, 0.0) + np.abs(rng.normal(0, 0.02, n)),
        "negative_daytime_consumption_ratio": np.where(pv, 0.5, 0.0) + np.abs(rng.normal(0, 0.03, n)),
        "total_export_kwh": np.where(pv, 3000.0, 0.0) + np.abs(rng.normal(0, 200, n)),
        "days_with_export_ratio": np.where(pv, 0.6, 0.0) + np.abs(rng.normal(0, 0.03, n)),
        "summer_midday_mean": np.where(pv, -1.5, 0.5) + z(0.2),
        "winter_midday_mean": 0.6 + z(0.2),
        "summer_vs_winter_midday_diff": np.where(pv, 2.0, 0.1) + z(0.2),
        "correlation_solar_radiation_consumption": np.where(pv, -0.6, 0.02) + z(0.08),
        "correlation_sunshine_duration_consumption": np.where(pv, -0.5, 0.0) + z(0.08),
        "sunny_day_midday_mean": np.where(pv, -2.0, 0.5) + z(0.2),
        "cloudy_day_midday_mean": 0.5 + z(0.2),
        "count_events_above_3kw": np.where(ev, 200, 20) + rng.normal(0, 10, n),
        "count_events_above_5kw": np.where(ev, 150, 8) + rng.normal(0, 8, n),
        "count_events_above_7kw": np.where(ev, 120, 2) + rng.normal(0, 5, n),
        "count_events_above_11kw": np.where(ev, 30, 0) + np.abs(rng.normal(0, 3, n)),
        "median_consumption": 0.4 + z(0.05),
        "p95_consumption": np.where(ev, 6.0, 2.0) + np.where(hp, 1.0, 0.0) + z(0.3),
        "p99_consumption": np.where(ev, 9.0, 3.0) + np.where(hp, 1.5, 0.0) + z(0.3),
        "max_consumption": np.where(ev, 11.0, 5.0) + z(0.5),
        "max_positive_ramp": np.where(ev, 8.0, 3.0) + z(0.5),
        "max_negative_ramp": -np.where(ev, 8.0, 3.0) + z(0.5),
        "p95_positive_ramp": np.where(ev, 3.0, 1.0) + z(0.2),
        "p99_positive_ramp": np.where(ev, 6.0, 2.0) + z(0.2),
        "p95_negative_ramp": np.where(ev, 3.0, 1.0) + z(0.2),
        "p99_negative_ramp": np.where(ev, 6.0, 2.0) + z(0.2),
        "session_mean": np.where(ev, 7.0, 3.5) + z(0.3),
        "session_median": np.where(ev, 7.0, 3.5) + z(0.3),
        "session_std": np.where(ev, 0.5, 1.0) + np.abs(z(0.1)),
        "session_variance": np.where(ev, 0.25, 1.0) + np.abs(z(0.1)),
        "session_cv": np.where(ev, 0.08, 0.3) + np.abs(z(0.03)),
        "morning_start_ratio": 0.2 + z(0.05),
        "midday_start_ratio": 0.2 + z(0.05),
        "evening_start_ratio": np.where(ev, 0.45, 0.25) + z(0.05),
        "night_start_ratio": np.where(ev, 0.25, 0.1) + z(0.05),
        "morning_finish_ratio": 0.2 + z(0.05),
        "midday_finish_ratio": 0.2 + z(0.05),
        "evening_finish_ratio": 0.3 + z(0.05),
        "night_finish_ratio": np.where(ev, 0.4, 0.15) + z(0.05),
        "morning_high_load_ratio": 0.2 + z(0.05),
        "midday_high_load_ratio": 0.2 + z(0.05),
        "evening_high_load_ratio": np.where(ev, 0.45, 0.3) + z(0.05),
        "night_high_load_ratio": np.where(ev, 0.25, 0.1) + z(0.05),
        "sessions_per_week": np.where(ev, 2.5, 0.1) + np.abs(rng.normal(0, 0.4, n)),
        "correlation_outside_temperature_consumption": np.where(hp, -0.55, -0.05) + z(0.08),
        "mean_consumption_T_below_minus5": np.where(hp, 2.5, 0.6) + z(0.2),
        "mean_consumption_T_minus5_to_0": np.where(hp, 2.0, 0.6) + z(0.2),
        "mean_consumption_T_0_to_5": np.where(hp, 1.6, 0.55) + z(0.2),
        "mean_consumption_T_5_to_10": np.where(hp, 1.2, 0.5) + z(0.2),
        "mean_consumption_T_10_to_15": np.where(hp, 0.8, 0.5) + z(0.2),
        "mean_consumption_T_above_15": 0.45 + z(0.1),
        "winter_night_mean_consumption": np.where(hp, 1.8, 0.4) + z(0.15),
        "summer_night_mean_consumption": 0.35 + z(0.1),
    }
    idx = np.arange(n)
    unlabeled = idx % unlabeled_every == 0
    known_unknown = (idx % 7 == 1) & ~unlabeled  # one flag missing while the others are known
    flags, raw_flags = {}, {}
    for a in ASSETS:
        f = truth[a].astype(float)
        f[unlabeled] = np.nan
        if a == "ev":
            f[known_unknown] = np.nan
        raw_flags[a] = f
        flags[LABEL_COLUMN[a]] = pl.Series([None if np.isnan(x) else int(x) for x in f], dtype=pl.Int8)
    # a few late installs: the flag says yes but the asset arrived after the window
    late = (idx % late_every == 0) & ~unlabeled
    for a in ASSETS:
        truth[a] = truth[a] & ~late  # late installs are not visible, the data behaves like "no asset"
    feats = pl.DataFrame(
        {
            "gp_nr": idx + 1000,
            "plz": ["5000"] * n,
            "num_mp_ids": np.ones(n, dtype=int),
            "n_valid_days": np.full(n, 900),
            **cols,
            **flags,
        }
    ).cast(
        {
            "gp_nr": pl.Int64,
            "num_mp_ids": pl.Int32,
            "n_valid_days": pl.Int32,
        }
    )
    # rewrite the informative columns for late installs so the data says "no asset" while the flag says yes
    feats = _apply_truth(feats, truth, rng)
    dates = pl.DataFrame(
        {
            "gp_nr": (idx + 1000).astype(np.int64),
            **{
                DATE_COLUMN[a]: [
                    date(2026, 3, 1) if (late[i] and raw_flags[a][i] == 1) else None for i in idx
                ]
                for a in ASSETS
            },
        },
        schema={"gp_nr": pl.Int64, **{c: pl.Date for c in DATE_COLUMN.values()}},
    )
    return feats.select(FEATURE_DATASET_COLUMNS), dates, truth


def _apply_truth(feats: pl.DataFrame, truth: dict[str, np.ndarray], rng: np.random.Generator) -> pl.DataFrame:
    """Late installs behave like non-owners: their informative columns come from the "no" distribution."""
    n = feats.height
    no = {
        "pv": {
            "negative_consumption_ratio": np.abs(rng.normal(0, 0.02, n)),
            "days_with_export_ratio": np.abs(rng.normal(0, 0.03, n)),
            "total_export_kwh": np.abs(rng.normal(0, 200, n)),
            "correlation_solar_radiation_consumption": 0.02 + rng.normal(0, 0.08, n),
            "sunny_day_midday_mean": 0.5 + rng.normal(0, 0.2, n),
            "summer_midday_mean": 0.5 + rng.normal(0, 0.2, n),
            "daytime_mean_power": 0.6 + rng.normal(0, 0.2, n),
        },
        "ev": {
            "sessions_per_week": 0.1 + np.abs(rng.normal(0, 0.4, n)),
            "count_events_above_7kw": 2 + rng.normal(0, 5, n),
            "session_median": 3.5 + rng.normal(0, 0.3, n),
            "p99_consumption": 3.0 + rng.normal(0, 0.3, n),
        },
        "heat_pump": {
            "correlation_outside_temperature_consumption": -0.05 + rng.normal(0, 0.08, n),
            "mean_consumption_T_below_minus5": 0.6 + rng.normal(0, 0.2, n),
            "winter_night_mean_consumption": 0.4 + rng.normal(0, 0.15, n),
        },
        "battery": {
            "near_zero_interval_ratio": 0.05 + rng.normal(0, 0.03, n),
            "evening_near_zero_ratio": 0.03 + rng.normal(0, 0.04, n),
            "daytime_near_zero_ratio": 0.08 + rng.normal(0, 0.04, n),
        },
    }
    label = {a: feats[LABEL_COLUMN[a]].to_numpy() for a in ASSETS}
    for a, repl in no.items():
        late = (label[a] == 1) & ~truth[a]
        if not late.any():
            continue
        feats = feats.with_columns(
            pl.Series(c, np.where(late, v, feats[c].to_numpy())) for c, v in repl.items()
        )
    return feats
