"""Battery / PV / EV / heat-pump feature expressions.

These functions only *measure* characteristics of a building's timeline —
none of them decide "this building has a PV/EV/battery/heat pump". That
judgement is left to a future ML model, per the brief.

Everything here is a `polars` expression evaluated inside one
``group_by("gp_nr").agg([...])`` (see ``pipeline.py``), so it is vectorised
and streams instead of looping over buildings in Python.

Weather alignment note: an hourly weather value is broadcast to the four
quarter-hours of that hour when joined onto the 15-minute consumption frame.
That is fine for row-level use (a per-interval ratio, or a correlation with
``power_kw``) but this module never *sums* a weather column across those
replicated rows — daily radiation sums for the sunny/cloudy classification
are computed once in ``weather.py`` from the hourly frame directly.
"""

from __future__ import annotations

import polars as pl

from feature_pipeline.config import PipelineConfig
from feature_pipeline.runs import add_run_columns, block_start_flag
from feature_pipeline.timeutil import add_calendar_columns, temperature_bin_expr
from feature_pipeline.weather import WeatherData

_EV_THRESHOLD_PREFIXES = {3.0: "ev3", 5.0: "ev5", 7.0: "ev7", 11.0: "ev11"}


def _safe_ratio(numerator: pl.Expr, denominator: pl.Expr) -> pl.Expr:
    return pl.when(denominator > 0).then(numerator / denominator).otherwise(None)


def _corr_with_min_obs(a: pl.Expr, b: pl.Expr, cond: pl.Expr, min_obs: int) -> pl.Expr:
    n = cond.sum()
    return (
        pl.when(n >= min_obs)
        .then(pl.corr(a.filter(cond), b.filter(cond)))
        .otherwise(None)
    )


def prepare_frame(lf: pl.LazyFrame, weather: WeatherData, cfg: PipelineConfig) -> pl.LazyFrame:
    """Sort, attach calendar/weather columns, and add every run/ramp column.

    Input: ``gp_nr, ts, power_kw, plz, num_mp_with_data``. Must be called
    once per building cohort before ``main_feature_exprs`` is used in a
    ``group_by("gp_nr")``.
    """
    th = cfg.thresholds
    lf = lf.sort(["gp_nr", "ts"])
    lf = add_calendar_columns(lf, "ts")

    lf = lf.join(
        weather.hourly.lazy(), left_on=["plz", "_ts_hour"], right_on=["plz", "ts"], how="left"
    )
    lf = lf.join(weather.daily_sun_class.lazy(), left_on=["plz", "_date"], right_on=["plz", "_date"], how="left")
    lf = lf.with_columns(
        pl.col("is_sunny_day").fill_null(False),
        pl.col("is_cloudy_day").fill_null(False),
    )

    # Joins do not guarantee the (gp_nr, ts) row order survives, and every
    # run/ramp computation below depends on it — re-sort before touching any
    # ``.over("gp_nr")`` window expression.
    lf = lf.sort(["gp_nr", "ts"])

    lf = lf.with_columns(temperature_bin_expr("temperature_2m", th).alias("_temp_bin"))

    # --- condition columns (nulls treated as "condition not met", never as
    # zero, since the surrounding valid-interval counts already account for
    # missing data) ---
    lf = lf.with_columns(
        (pl.col("power_kw").abs() <= th.near_zero_epsilon_kw).fill_null(False).alias("is_near_zero"),
        *[
            (pl.col("power_kw") > threshold).fill_null(False).alias(f"is_{prefix}")
            for threshold, prefix in _EV_THRESHOLD_PREFIXES.items()
        ],
        (pl.col("power_kw") >= th.ev_session_threshold_kw).fill_null(False).alias("is_high_load"),
    )

    for prefix in ("near_zero", *_EV_THRESHOLD_PREFIXES.values()):
        cond_col = "is_near_zero" if prefix == "near_zero" else f"is_{prefix}"
        run_prefix = "nz" if prefix == "near_zero" else prefix
        lf = add_run_columns(lf, cond_col=cond_col, prefix=run_prefix, interval_minutes=th.interval_minutes)

    # --- ramps: only across exactly-15-minute gaps, never across a missing
    # interval ---
    gap_ok = (pl.col("ts").diff().over("gp_nr") == pl.duration(minutes=th.interval_minutes))
    lf = lf.with_columns(
        pl.when(gap_ok).then(pl.col("power_kw").diff().over("gp_nr")).otherwise(None).alias("ramp")
    )

    return lf


def main_feature_exprs(cfg: PipelineConfig) -> list[pl.Expr]:
    th = cfg.thresholds
    valid = pl.col("power_kw").is_not_null()
    exprs: list[pl.Expr] = [
        pl.len().alias("_n_rows_total"),
        valid.sum().alias("num_valid_intervals"),
        pl.col("ts").min().alias("min_ts"),
        pl.col("ts").max().alias("max_ts"),
    ]

    # ---------------- Battery ----------------
    exprs += [
        pl.lit(None, dtype=pl.Float64).alias("pv_presence"),  # TODO: replace with
        # out-of-fold P(PV) once the PV classifier exists (battery model
        # second stage). Ground-truth PV label must never be used here.
        _safe_ratio(pl.col("is_near_zero").sum(), valid.sum()).alias("near_zero_interval_ratio"),
        block_start_flag("nz", "is_near_zero", th.near_zero_min_intervals)
        .sum()
        .alias("number_of_near_zero_blocks"),
        _safe_ratio(
            (pl.col("is_near_zero") & pl.col("is_midday")).sum(),
            (valid & pl.col("is_midday")).sum(),
        ).alias("daytime_near_zero_ratio"),
        _safe_ratio(
            (pl.col("is_near_zero") & pl.col("is_evening")).sum(),
            (valid & pl.col("is_evening")).sum(),
        ).alias("evening_near_zero_ratio"),
        (pl.col("power_kw") / pl.col("shortwave_radiation"))
        .filter(valid & (pl.col("shortwave_radiation") >= th.solar_radiation_min_wm2))
        .median()
        .alias("consumption_per_unit_solar_radiation"),
    ]

    # ---------------- PV ----------------
    exprs += [
        pl.col("power_kw").filter(pl.col("is_midday")).mean().alias("daytime_mean_power"),
        pl.col("power_kw").filter(pl.col("is_morning")).mean().alias("morning_mean_power"),
        pl.col("power_kw").filter(pl.col("is_evening")).mean().alias("evening_mean_power"),
        _safe_ratio(
            (pl.col("power_kw") < -th.export_epsilon_kw).sum(), valid.sum()
        ).alias("negative_consumption_ratio"),
        _safe_ratio(
            ((pl.col("power_kw") < -th.export_epsilon_kw) & pl.col("is_midday")).sum(),
            (valid & pl.col("is_midday")).sum(),
        ).alias("negative_daytime_consumption_ratio"),
        (
            (-pl.col("power_kw")).filter(pl.col("power_kw") < 0).sum()
            * (th.interval_minutes / 60.0)
        ).alias("total_export_kwh"),
        pl.col("power_kw").filter(pl.col("is_midday") & pl.col("is_summer")).mean().alias(
            "summer_midday_mean"
        ),
        pl.col("power_kw").filter(pl.col("is_midday") & pl.col("is_winter")).mean().alias(
            "winter_midday_mean"
        ),
        _corr_with_min_obs(
            pl.col("power_kw"),
            pl.col("shortwave_radiation"),
            valid & (pl.col("shortwave_radiation") >= th.solar_radiation_min_wm2),
            th.corr_min_observations,
        ).alias("correlation_solar_radiation_consumption"),
        _corr_with_min_obs(
            pl.col("power_kw"),
            pl.col("sunshine_duration"),
            valid & pl.col("sunshine_duration").is_not_null(),
            th.corr_min_observations,
        ).alias("correlation_sunshine_duration_consumption"),
        pl.col("power_kw")
        .filter(pl.col("is_midday") & pl.col("is_sunny_day"))
        .mean()
        .alias("sunny_day_midday_mean"),
        pl.col("power_kw")
        .filter(pl.col("is_midday") & pl.col("is_cloudy_day"))
        .mean()
        .alias("cloudy_day_midday_mean"),
    ]

    # ---------------- EV: high-load event counts + distribution + ramps ----
    for threshold, prefix in _EV_THRESHOLD_PREFIXES.items():
        exprs.append(
            block_start_flag(prefix, f"is_{prefix}", th.ev_min_event_intervals)
            .sum()
            .alias(f"count_events_above_{int(threshold)}kw")
        )

    exprs += [
        pl.col("power_kw").filter(valid).median().alias("median_consumption"),
        pl.col("power_kw").filter(valid).quantile(0.95).alias("p95_consumption"),
        pl.col("power_kw").filter(valid).quantile(0.99).alias("p99_consumption"),
        pl.col("power_kw").filter(valid).max().alias("max_consumption"),
        pl.col("ramp").filter(pl.col("ramp") > 0).max().alias("max_positive_ramp"),
        pl.col("ramp").filter(pl.col("ramp") < 0).min().alias("max_negative_ramp"),
        pl.col("ramp").filter(pl.col("ramp") > 0).quantile(0.95).alias("p95_positive_ramp"),
        pl.col("ramp").filter(pl.col("ramp") > 0).quantile(0.99).alias("p99_positive_ramp"),
        (-pl.col("ramp")).filter(pl.col("ramp") < 0).quantile(0.95).alias("p95_negative_ramp"),
        (-pl.col("ramp")).filter(pl.col("ramp") < 0).quantile(0.99).alias("p99_negative_ramp"),
    ]

    for w in cfg.windows.all():
        exprs.append(
            _safe_ratio(
                (pl.col("is_high_load") & pl.col(f"is_{w.name}")).sum(),
                pl.col("is_high_load").sum(),
            ).alias(f"{w.name}_high_load_ratio")
        )

    # ---------------- Heat pump ----------------
    exprs.append(
        _corr_with_min_obs(
            pl.col("power_kw"),
            pl.col("temperature_2m"),
            valid & pl.col("temperature_2m").is_not_null(),
            th.corr_min_observations,
        ).alias("correlation_outside_temperature_consumption")
    )
    for tb in th.temperature_bins:
        cond = valid & (pl.col("_temp_bin") == tb.name)
        n = cond.sum()
        exprs.append(
            pl.when(n >= th.min_temp_bin_observations)
            .then(pl.col("power_kw").filter(cond).mean())
            .otherwise(None)
            .alias(f"mean_consumption_T_{tb.name}")
        )
    exprs += [
        pl.col("power_kw").filter(pl.col("is_winter") & pl.col("is_night")).mean().alias(
            "winter_night_mean_consumption"
        ),
        pl.col("power_kw").filter(pl.col("is_summer") & pl.col("is_night")).mean().alias(
            "summer_night_mean_consumption"
        ),
    ]

    return exprs


def day_level_export_ratio(lf: pl.LazyFrame, cfg: PipelineConfig) -> pl.LazyFrame:
    """``days_with_export_ratio`` needs a *day* count, not an interval count,

    so it gets its own small group_by(gp_nr, date) pass before folding down
    to one row per building.
    """
    th = cfg.thresholds
    per_day = lf.group_by(["gp_nr", "_date"]).agg(
        pl.col("power_kw").is_not_null().any().alias("_has_valid"),
        (pl.col("power_kw") < -th.export_epsilon_kw).fill_null(False).any().alias("_has_export"),
    )
    return per_day.group_by("gp_nr").agg(
        _safe_ratio(pl.col("_has_export").sum(), pl.col("_has_valid").sum()).alias(
            "days_with_export_ratio"
        )
    )


def finalize_pv_diff(df: pl.DataFrame) -> pl.DataFrame:
    """``summer_vs_winter_midday_diff`` combines two other output columns, so

    it is added after the aggregation rather than inside a single ``agg()``
    (aggregation expressions cannot reference each other's results).
    """
    return df.with_columns(
        (pl.col("winter_midday_mean") - pl.col("summer_midday_mean")).alias(
            "summer_vs_winter_midday_diff"
        )
    )
