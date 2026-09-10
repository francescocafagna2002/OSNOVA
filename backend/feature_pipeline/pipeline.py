"""End-to-end orchestration: raw consumption + mappings + weather + labels

-> ``feature_dataset.parquet`` (+ ``ev_candidate_sessions.parquet`` debug output).

One row per GP-Nr (building). No model training, SHAP or predictions happen
here — see ``backend/feature_pipeline/README.md`` for the scope of this task.
"""

from __future__ import annotations

import logging
import time

import polars as pl

from feature_pipeline.audit import AuditReport, compute_nan_counts, print_audit_report, write_audit_report
from feature_pipeline.config import PipelineConfig
from feature_pipeline.features import (
    day_level_export_ratio,
    finalize_pv_diff,
    main_feature_exprs,
    prepare_frame,
)
from feature_pipeline.ingest import discover_consumption_files, run_ingest, scan_building_consumption
from feature_pipeline.labels import load_labels
from feature_pipeline.mapping import load_mapping
from feature_pipeline.sessions import add_session_run_columns, aggregate_sessions_to_building, build_session_table
from feature_pipeline.weather import load_weather

logger = logging.getLogger(__name__)

# Final column order. "at least" these per the brief — kept explicit so a
# schema change is a one-line diff to review, not a silent reorder.
FINAL_COLUMNS = [
    "gp_nr",
    "plz",
    "num_mp_ids",
    # Battery
    "pv_presence",
    "near_zero_interval_ratio",
    "number_of_near_zero_blocks",
    "daytime_near_zero_ratio",
    "evening_near_zero_ratio",
    "consumption_per_unit_solar_radiation",
    # PV
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
    # EV
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
    # Heat pump
    "correlation_outside_temperature_consumption",
    "mean_consumption_T_below_minus5",
    "mean_consumption_T_minus5_to_0",
    "mean_consumption_T_0_to_5",
    "mean_consumption_T_5_to_10",
    "mean_consumption_T_10_to_15",
    "mean_consumption_T_above_15",
    "winter_night_mean_consumption",
    "summer_night_mean_consumption",
    # Labels
    "label_pv",
    "label_ev",
    "label_heatpump",
    "label_battery",
]


def run_pipeline(
    cfg: PipelineConfig,
    limit_buildings: int | None = None,
    limit_files: int | None = None,
    resume: bool = True,
) -> AuditReport:
    start = time.monotonic()
    report = AuditReport()

    logger.info("Loading MP -> building mapping")
    mapping = load_mapping(cfg.paths)
    report.number_of_unresolved_mapping_mp_ids = len(mapping.unresolved_mp_ids)
    report.number_of_ambiguous_mapping_mp_ids = len(mapping.ambiguous_mp_ids)
    report.number_of_buildings_in_mapping = mapping.building_mp_counts.height

    mp_to_building = mapping.mp_to_building
    building_mp_counts = mapping.building_mp_counts
    if limit_buildings is not None:
        sampled = (
            building_mp_counts.sort("gp_nr").head(limit_buildings).get_column("gp_nr").to_list()
        )
        mp_to_building = mp_to_building.filter(pl.col("gp_nr").is_in(sampled))
        building_mp_counts = building_mp_counts.filter(pl.col("gp_nr").is_in(sampled))
        logger.info("Dev run: limited to %d buildings", len(sampled))

    logger.info("Loading device labels")
    labels = load_labels(cfg.paths)

    logger.info("Loading weather")
    weather = load_weather(cfg.paths, cfg.thresholds)
    report.number_of_weather_plz = len(weather.plz_with_weather)

    report.number_of_consumption_files = len(discover_consumption_files(cfg.paths))
    logger.info("Ingesting raw consumption (%d files discovered)", report.number_of_consumption_files)
    ingest_audit = run_ingest(
        cfg.paths, cfg.thresholds, mp_to_building, limit_files=limit_files, resume=resume
    )
    report.number_of_files_processed_this_run = ingest_audit.files_processed_this_run
    report.number_of_files_skipped_cached = ingest_audit.files_skipped_cached
    report.number_of_files_failed = len(ingest_audit.files_failed)
    report.failed_files = list(ingest_audit.files_failed)
    report.number_of_mapped_mp_ids = len(ingest_audit.mapped_mp_ids_seen)
    report.number_of_unmapped_mp_ids = len(ingest_audit.unmapped_mp_ids)
    report.sample_unmapped_mp_ids = sorted(ingest_audit.unmapped_mp_ids)[:20]

    base = scan_building_consumption(cfg.paths)
    prepared = prepare_frame(base, weather, cfg)

    logger.info("Computing per-building features")
    main_exprs = main_feature_exprs(cfg)
    main_df = prepared.group_by("gp_nr").agg(main_exprs).collect()
    main_df = finalize_pv_diff(main_df)

    date_min = main_df.get_column("min_ts").min()
    date_max = main_df.get_column("max_ts").max()
    report.date_range_min = str(date_min) if date_min is not None else None
    report.date_range_max = str(date_max) if date_max is not None else None

    coverage = main_df.lazy().select("gp_nr", "min_ts", "max_ts")

    day_export = day_level_export_ratio(prepared, cfg).collect()

    logger.info("Detecting EV candidate sessions")
    with_session_runs = add_session_run_columns(prepared, cfg)
    sessions_table = build_session_table(with_session_runs, cfg).collect()
    sessions_table.write_parquet(cfg.paths.sessions_debug_path)
    session_features = aggregate_sessions_to_building(sessions_table.lazy(), coverage, cfg).collect()

    # --- assemble one row per building ---
    plz_lookup = (
        base.select("gp_nr", "plz").unique(subset=["gp_nr"], keep="first").collect()
    )

    feature_df = (
        main_df.drop("_n_rows_total", "min_ts", "max_ts")
        .join(day_export, on="gp_nr", how="left")
        .join(session_features, on="gp_nr", how="left")
        .join(plz_lookup, on="gp_nr", how="left")
        .join(building_mp_counts, on="gp_nr", how="left")
        .join(labels, on="gp_nr", how="left")
    )

    report.number_of_processed_buildings = feature_df.height
    report.number_of_multi_mp_buildings = (
        feature_df.filter(pl.col("num_mp_ids") > 1).height
    )
    building_plz = feature_df.get_column("plz").drop_nulls().unique().to_list()
    report.number_of_building_plz = len(building_plz)
    report.number_of_building_plz_without_weather = sum(
        1 for p in building_plz if p not in weather.plz_with_weather
    )

    # A building with zero detected sessions gets nulls from the left join
    # for every session_* column; session_count and sessions_per_week have a
    # well-defined zero, the power/timing stats stay null (no data, not 0).
    feature_df = feature_df.with_columns(
        pl.col("session_count").fill_null(0),
        pl.col("sessions_per_week").fill_null(0.0),
    )

    missing_cols = [c for c in FINAL_COLUMNS if c not in feature_df.columns]
    if missing_cols:
        raise RuntimeError(f"Feature dataset is missing expected columns: {missing_cols}")

    feature_df = feature_df.select(FINAL_COLUMNS)

    cfg.paths.output_dir.mkdir(parents=True, exist_ok=True)
    feature_df.write_parquet(cfg.paths.feature_dataset_path)

    report.nan_counts = compute_nan_counts(feature_df)
    report.processing_time_seconds = time.monotonic() - start

    write_audit_report(cfg.paths.audit_path, report)
    print_audit_report(report)

    return report
