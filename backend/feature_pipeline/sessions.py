"""EV candidate-session detection and its building-level aggregation.

A session is a continuous block of quarter-hours at/above
``ev_session_threshold_kw`` lasting at least ``ev_min_session_minutes``,
never bridging a missing-timestamp gap (``runs.py``). This module:

1. builds ``ev_candidate_sessions.parquet`` — one row per detected session,
   an intermediate debugging output, not part of the ML feature set;
2. aggregates the (variable-length) session list of each building into the
   fixed-size ``session_*`` / start-finish-ratio / ``sessions_per_week``
   feature columns.

This is a candidate detector only: it measures where "sustained high load"
happens, it does not decide "this building has an EV" — that judgement is
left to a future model, per the brief.
"""

from __future__ import annotations

import polars as pl

from feature_pipeline.config import PipelineConfig
from feature_pipeline.runs import add_run_columns
from feature_pipeline.timeutil import daypart_expr

_SESSION_PREFIX = "evsess"


def add_session_run_columns(lf: pl.LazyFrame, cfg: PipelineConfig) -> pl.LazyFrame:
    """Frame must already be sorted by (gp_nr, ts) and carry the ``is_high_load``

    column added by ``features.prepare_frame`` (``power_kw >= ev_session_threshold_kw``,
    the same primary EV threshold used by the high-load-ratio features).
    """
    return add_run_columns(
        lf,
        cond_col="is_high_load",
        prefix=_SESSION_PREFIX,
        interval_minutes=cfg.thresholds.interval_minutes,
    )


def build_session_table(lf_with_runs: pl.LazyFrame, cfg: PipelineConfig) -> pl.LazyFrame:
    """One row per qualifying session: start/end/duration/power stats/energy."""
    th = cfg.thresholds
    qualifying = lf_with_runs.filter(
        pl.col("is_high_load")
        & (pl.col(f"{_SESSION_PREFIX}_run_len") >= th.ev_min_session_intervals)
    )
    sessions = qualifying.group_by(["gp_nr", f"{_SESSION_PREFIX}_run_id"]).agg(
        pl.col("ts").min().alias("start_timestamp"),
        (pl.col("ts").max() + pl.duration(minutes=th.interval_minutes)).alias("end_timestamp"),
        pl.len().alias("_n_intervals"),
        pl.col("power_kw").mean().alias("mean_power"),
        pl.col("power_kw").median().alias("median_power"),
        pl.col("power_kw").std().alias("std_power"),
        pl.col("power_kw").var().alias("variance_power"),
        (pl.col("power_kw").sum() * (th.interval_minutes / 60.0)).alias("energy_kwh"),
    )
    sessions = sessions.with_columns(
        (pl.col("_n_intervals") * th.interval_minutes).alias("duration_minutes"),
        pl.when(pl.col("mean_power") != 0)
        .then(pl.col("std_power") / pl.col("mean_power"))
        .otherwise(None)
        .alias("cv_power"),
    ).drop("_n_intervals", f"{_SESSION_PREFIX}_run_id")
    return sessions


def aggregate_sessions_to_building(
    sessions_lf: pl.LazyFrame, coverage_lf: pl.LazyFrame, cfg: PipelineConfig
) -> pl.LazyFrame:
    """Fold the variable-length session list into fixed building-level columns."""
    windows = cfg.windows.all()

    with_hours = sessions_lf.with_columns(
        pl.col("start_timestamp").dt.hour().alias("_start_hour"),
        pl.col("end_timestamp").dt.hour().alias("_end_hour"),
    )
    start_flags = [daypart_expr("_start_hour", w).alias(f"_start_is_{w.name}") for w in windows]
    end_flags = [daypart_expr("_end_hour", w).alias(f"_end_is_{w.name}") for w in windows]
    with_hours = with_hours.with_columns(start_flags + end_flags)

    agg_exprs = [
        pl.len().alias("session_count"),
        pl.col("mean_power").mean().alias("session_mean"),
        pl.col("mean_power").median().alias("session_median"),
        pl.col("mean_power").std().alias("session_std"),
        pl.col("mean_power").var().alias("session_variance"),
    ]
    for w in windows:
        agg_exprs.append(pl.col(f"_start_is_{w.name}").sum().alias(f"_n_start_{w.name}"))
        agg_exprs.append(pl.col(f"_end_is_{w.name}").sum().alias(f"_n_end_{w.name}"))

    per_building = with_hours.group_by("gp_nr").agg(agg_exprs)

    per_building = per_building.with_columns(
        pl.when(pl.col("session_mean") != 0)
        .then(pl.col("session_std") / pl.col("session_mean"))
        .otherwise(None)
        .alias("session_cv")
    )

    ratio_exprs = []
    for w in windows:
        ratio_exprs.append(
            pl.when(pl.col("session_count") > 0)
            .then(pl.col(f"_n_start_{w.name}") / pl.col("session_count"))
            .otherwise(None)
            .alias(f"{w.name}_start_ratio")
        )
        ratio_exprs.append(
            pl.when(pl.col("session_count") > 0)
            .then(pl.col(f"_n_end_{w.name}") / pl.col("session_count"))
            .otherwise(None)
            .alias(f"{w.name}_finish_ratio")
        )
    per_building = per_building.with_columns(ratio_exprs).drop(
        [f"_n_start_{w.name}" for w in windows] + [f"_n_end_{w.name}" for w in windows]
    )

    per_building = per_building.join(coverage_lf, on="gp_nr", how="left")
    weeks = (
        pl.col("max_ts") - pl.col("min_ts")
    ).dt.total_seconds() / (7 * 24 * 3600)
    per_building = per_building.with_columns(
        pl.when(weeks > 0)
        .then(pl.col("session_count") / weeks)
        .otherwise(None)
        .alias("sessions_per_week")
    ).drop("min_ts", "max_ts")

    return per_building
