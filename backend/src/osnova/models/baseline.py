# src/osnova/models/baseline.py
"""Rule-based baseline scores per asset, reported next to the model so the gain is visible."""

from __future__ import annotations

import polars as pl
from pydantic import BaseModel

from osnova.config import ASSETS

BASE_COLUMNS = [f"base_{a}" for a in ASSETS]


class BaselineConfig(BaseModel):
    """Weighted thresholds on the team's feature names. Missing columns or nulls count as false."""

    export_days_ratio_min: float = 0.05  # days_with_export_ratio above this = "export present"
    radiation_corr_max: float = -0.4  # correlation_solar_radiation_consumption below this = PV-like
    ev_sessions_per_week_min: float = 1.0
    ev_session_kw_min: float = 3.0
    hp_night_ratio_min: float = 2.0  # winter night load / summer night load
    hp_temperature_corr_max: float = -0.3
    battery_evening_near_zero_min: float = 0.15
    pv_with_export: float = 0.9
    pv_without_export: float = 0.2
    pv_radiation_bonus: float = 0.5
    ev_yes: float = 0.85
    ev_no: float = 0.15
    hp_yes: float = 0.8
    hp_no: float = 0.15
    battery_yes: float = 0.7
    battery_no: float = 0.1


def _col(features: pl.DataFrame, name: str) -> pl.Expr:
    return pl.col(name).cast(pl.Float64) if name in features.columns else pl.lit(None, dtype=pl.Float64)


def baseline_scores(features: pl.DataFrame, cfg: BaselineConfig | None = None) -> pl.DataFrame:
    """gp_nr + base_<asset> in 0..1 for every feature row."""
    c = cfg or BaselineConfig()
    f = lambda name: _col(features, name)  # noqa: E731
    export_present = (f("days_with_export_ratio") > c.export_days_ratio_min).fill_null(False)
    pv_like = (
        (f("correlation_solar_radiation_consumption") < c.radiation_corr_max)
        & (f("sunny_day_midday_mean") < f("cloudy_day_midday_mean"))
    ).fill_null(False)
    ev_like = (
        (f("sessions_per_week") >= c.ev_sessions_per_week_min) & (f("session_median") >= c.ev_session_kw_min)
    ).fill_null(False)
    hp_like = (
        (f("winter_night_mean_consumption") > c.hp_night_ratio_min * f("summer_night_mean_consumption"))
        & (f("correlation_outside_temperature_consumption") < c.hp_temperature_corr_max)
    ).fill_null(False)
    battery_like = export_present & (
        f("evening_near_zero_ratio") > c.battery_evening_near_zero_min
    ).fill_null(False)
    return features.select(
        pl.col("gp_nr").cast(pl.Int64),
        pl.when(export_present)
        .then(c.pv_with_export)
        .otherwise((c.pv_without_export + c.pv_radiation_bonus * pv_like.cast(pl.Float64)).clip(0.0, 1.0))
        .alias("base_pv"),
        pl.when(battery_like).then(c.battery_yes).otherwise(c.battery_no).alias("base_battery"),
        pl.when(hp_like).then(c.hp_yes).otherwise(c.hp_no).alias("base_heat_pump"),
        pl.when(ev_like).then(c.ev_yes).otherwise(c.ev_no).alias("base_ev"),
    )
