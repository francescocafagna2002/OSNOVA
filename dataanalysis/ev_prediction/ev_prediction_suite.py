import numpy as np
import pandas as pd


def extract_ev_features(
    raw_timeseries: pd.DataFrame
) -> pd.DataFrame:
    """
    Extract EV-charging-related features from wide-format
    15-minute electricity time series.

    Expected input columns:
        MP ID
        Datum
        00:00
        00:15
        ...
        23:45

    Returns:
        One row of engineered features per MP ID.
    """

    df = raw_timeseries.copy()

    # ========================================================
    # 1. BASIC CLEANUP
    # ========================================================

    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
    )

    required_columns = {
        "MP ID",
        "Datum",
    }

    missing_required = (
        required_columns
        - set(df.columns)
    )

    if missing_required:
        raise ValueError(
            f"Missing required columns: "
            f"{sorted(missing_required)}"
        )

    df["MP ID"] = pd.to_numeric(
        df["MP ID"],
        errors="coerce"
    ).astype("Int64")

    df["Datum"] = pd.to_datetime(
        df["Datum"],
        dayfirst=True,
        errors="coerce"
    )

    df = (
        df
        .dropna(
            subset=[
                "MP ID",
                "Datum",
            ]
        )
        .copy()
    )

    if df.empty:
        raise ValueError(
            "No valid rows remain after parsing MP ID and Datum."
        )

    # ========================================================
    # 2. FIND 15-MINUTE COLUMNS
    # ========================================================

    expected_time_cols = [
        f"{hour:02d}:{minute:02d}"
        for hour in range(24)
        for minute in (
            0,
            15,
            30,
            45,
        )
    ]

    # Selecting this way also puts the time columns
    # into chronological order.
    time_cols = [
        col
        for col in expected_time_cols
        if col in df.columns
    ]

    if not time_cols:
        raise ValueError(
            "No 15-minute measurement columns found."
        )

    if len(time_cols) < 2:
        raise ValueError(
            "At least two 15-minute measurement columns "
            "are required."
        )

    print(
        f"Found {len(time_cols)} / 96 "
        f"15-minute columns"
    )

    # ========================================================
    # 3. CONVERT MEASUREMENTS TO NUMERIC
    # ========================================================

    df[time_cols] = (
        df[time_cols]
        .apply(
            pd.to_numeric,
            errors="coerce"
        )
    )

    # ========================================================
    # 4. TIME-OF-DAY GROUPS
    # ========================================================

    def get_hour(column_name: str) -> int:
        return int(
            column_name.split(":")[0]
        )

    night_cols = [
        col
        for col in time_cols
        if 0 <= get_hour(col) < 6
    ]

    morning_cols = [
        col
        for col in time_cols
        if 6 <= get_hour(col) < 10
    ]

    midday_cols = [
        col
        for col in time_cols
        if 10 <= get_hour(col) < 16
    ]

    afternoon_cols = [
        col
        for col in time_cols
        if 16 <= get_hour(col) < 18
    ]

    evening_cols = [
        col
        for col in time_cols
        if 18 <= get_hour(col) < 22
    ]

    late_evening_cols = [
        col
        for col in time_cols
        if 22 <= get_hour(col) < 24
    ]

    # ========================================================
    # 5. DAILY STATISTICS
    # ========================================================

    values = df[time_cols]

    df["daily_mean"] = (
        values.mean(axis=1)
    )

    df["daily_std"] = (
        values.std(axis=1)
    )

    df["daily_min"] = (
        values.min(axis=1)
    )

    df["daily_max"] = (
        values.max(axis=1)
    )

    df["daily_median"] = (
        values.median(axis=1)
    )

    df["daily_p90"] = (
        values.quantile(
            0.90,
            axis=1
        )
    )

    df["daily_p95"] = (
        values.quantile(
            0.95,
            axis=1
        )
    )

    df["daily_p99"] = (
        values.quantile(
            0.99,
            axis=1
        )
    )

    df["daily_range"] = (
        df["daily_max"]
        - df["daily_min"]
    )

    # ========================================================
    # 6. TIME-OF-DAY LOAD
    # ========================================================

    df["night_mean"] = (
        df[night_cols]
        .mean(axis=1)
    )

    df["morning_mean"] = (
        df[morning_cols]
        .mean(axis=1)
    )

    df["midday_mean"] = (
        df[midday_cols]
        .mean(axis=1)
    )

    df["afternoon_mean"] = (
        df[afternoon_cols]
        .mean(axis=1)
    )

    df["evening_mean"] = (
        df[evening_cols]
        .mean(axis=1)
    )

    df["late_evening_mean"] = (
        df[late_evening_cols]
        .mean(axis=1)
    )

    # ========================================================
    # 7. EV-RELATED RATIOS
    # ========================================================

    epsilon = 1e-6

    df["evening_day_ratio"] = (
        df["evening_mean"]
        /
        (
            df["daily_mean"]
            + epsilon
        )
    )

    df["night_day_ratio"] = (
        df["night_mean"]
        /
        (
            df["daily_mean"]
            + epsilon
        )
    )

    df["late_evening_day_ratio"] = (
        df["late_evening_mean"]
        /
        (
            df["daily_mean"]
            + epsilon
        )
    )

    df["evening_midday_ratio"] = (
        df["evening_mean"]
        /
        (
            df["midday_mean"]
            + epsilon
        )
    )

    # ========================================================
    # 8. PEAK CHARACTERISTICS
    # ========================================================

    df["peak_to_mean"] = (
        df["daily_max"]
        /
        (
            df["daily_mean"]
            + epsilon
        )
    )

    df["p95_to_median"] = (
        df["daily_p95"]
        /
        (
            df["daily_median"]
            + epsilon
        )
    )

    df["max_to_median"] = (
        df["daily_max"]
        /
        (
            df["daily_median"]
            + epsilon
        )
    )

    # ========================================================
    # 9. LOAD RAMPS
    # ========================================================

    matrix = values.to_numpy(
        dtype=float
    )

    differences = np.diff(
        matrix,
        axis=1
    )

    with np.errstate(
        all="ignore"
    ):
        df["max_positive_ramp"] = (
            np.nanmax(
                differences,
                axis=1
            )
        )

        df["max_negative_ramp"] = (
            np.nanmin(
                differences,
                axis=1
            )
        )

        df["mean_absolute_ramp"] = (
            np.nanmean(
                np.abs(differences),
                axis=1
            )
        )

    # ========================================================
    # 10. SUSTAINED LOAD
    #
    # 4 x 15 minutes = 1 hour
    # 8 x 15 minutes = 2 hours
    # ========================================================

    rolling_1h = (
        values
        .T
        .rolling(
            window=4,
            min_periods=4
        )
        .mean()
        .T
    )

    rolling_2h = (
        values
        .T
        .rolling(
            window=8,
            min_periods=8
        )
        .mean()
        .T
    )

    df["max_1h_mean"] = (
        rolling_1h
        .max(axis=1)
    )

    df["max_2h_mean"] = (
        rolling_2h
        .max(axis=1)
    )

    # ========================================================
    # 11. CALENDAR FEATURES
    # ========================================================

    df["weekday"] = (
        df["Datum"]
        .dt.weekday
    )

    df["is_weekend"] = (
        df["weekday"] >= 5
    )

    # ========================================================
    # 12. AGGREGATE TO ONE ROW PER MP ID
    # ========================================================

    features = (
        df
        .groupby("MP ID")
        .agg(
            number_of_days=(
                "Datum",
                "nunique"
            ),

            overall_mean=(
                "daily_mean",
                "mean"
            ),

            overall_std=(
                "daily_mean",
                "std"
            ),

            mean_daily_std=(
                "daily_std",
                "mean"
            ),

            mean_daily_max=(
                "daily_max",
                "mean"
            ),

            median_daily_max=(
                "daily_max",
                "median"
            ),

            max_daily_max=(
                "daily_max",
                "max"
            ),

            mean_daily_p95=(
                "daily_p95",
                "mean"
            ),

            max_daily_p95=(
                "daily_p95",
                "max"
            ),

            mean_daily_p99=(
                "daily_p99",
                "mean"
            ),

            mean_daily_range=(
                "daily_range",
                "mean"
            ),

            mean_night=(
                "night_mean",
                "mean"
            ),

            mean_morning=(
                "morning_mean",
                "mean"
            ),

            mean_midday=(
                "midday_mean",
                "mean"
            ),

            mean_afternoon=(
                "afternoon_mean",
                "mean"
            ),

            mean_evening=(
                "evening_mean",
                "mean"
            ),

            mean_late_evening=(
                "late_evening_mean",
                "mean"
            ),

            mean_evening_day_ratio=(
                "evening_day_ratio",
                "mean"
            ),

            mean_night_day_ratio=(
                "night_day_ratio",
                "mean"
            ),

            mean_late_evening_day_ratio=(
                "late_evening_day_ratio",
                "mean"
            ),

            mean_evening_midday_ratio=(
                "evening_midday_ratio",
                "mean"
            ),

            mean_peak_to_mean=(
                "peak_to_mean",
                "mean"
            ),

            mean_p95_to_median=(
                "p95_to_median",
                "mean"
            ),

            mean_max_to_median=(
                "max_to_median",
                "mean"
            ),

            mean_max_positive_ramp=(
                "max_positive_ramp",
                "mean"
            ),

            max_positive_ramp=(
                "max_positive_ramp",
                "max"
            ),

            mean_max_negative_ramp=(
                "max_negative_ramp",
                "mean"
            ),

            min_negative_ramp=(
                "max_negative_ramp",
                "min"
            ),

            mean_absolute_ramp=(
                "mean_absolute_ramp",
                "mean"
            ),

            mean_max_1h=(
                "max_1h_mean",
                "mean"
            ),

            max_1h=(
                "max_1h_mean",
                "max"
            ),

            mean_max_2h=(
                "max_2h_mean",
                "mean"
            ),

            max_2h=(
                "max_2h_mean",
                "max"
            ),
        )
        .reset_index()
    )

    # ========================================================
    # 13. WEEKDAY VS WEEKEND BEHAVIOR
    #
    # IMPORTANT:
    # False and True are actual COLUMN LABELS here.
    # We must use reindex(columns=...) rather than
    # weekend[[False, True]], because pandas may interpret
    # [False, True] as a boolean ROW mask.
    # ========================================================

    weekday_weekend = (
        df
        .groupby(
            [
                "MP ID",
                "is_weekend",
            ]
        )["evening_mean"]
        .mean()
        .unstack(
            "is_weekend"
        )
    )

    # Explicitly request the boolean-named columns.
    # Missing weekday/weekend data automatically becomes NaN.
    weekday_weekend = (
        weekday_weekend
        .reindex(
            columns=[
                False,
                True,
            ]
        )
    )

    weekday_weekend = (
        weekday_weekend
        .rename(
            columns={
                False:
                    "weekday_evening_mean",

                True:
                    "weekend_evening_mean",
            }
        )
        .reset_index()
    )

    features = (
        features
        .merge(
            weekday_weekend,
            on="MP ID",
            how="left"
        )
    )

    # Difference can sometimes be useful to the model.
    features[
        "weekend_weekday_evening_difference"
    ] = (
        features[
            "weekend_evening_mean"
        ]
        -
        features[
            "weekday_evening_mean"
        ]
    )

    # ========================================================
    # 14. AVERAGE 96-POINT DAILY LOAD PROFILE
    # ========================================================

    average_profile = (
        df
        .groupby("MP ID")[
            time_cols
        ]
        .mean()
        .reset_index()
    )

    average_profile = (
        average_profile
        .rename(
            columns={
                col:
                    f"profile_{col.replace(':', '_')}"
                for col in time_cols
            }
        )
    )

    features = (
        features
        .merge(
            average_profile,
            on="MP ID",
            how="left"
        )
    )

    # ========================================================
    # 15. CLEAN INVALID NUMBERS
    # ========================================================

    features = (
        features
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan
        )
    )

    return features


def predict_ev(
    raw_timeseries: pd.DataFrame,
    model,
    feature_columns
) -> pd.DataFrame:
    """
    Predict EV charger ownership for one or more MP IDs.

    raw_timeseries:
        Raw wide-format meter data.

    model:
        Trained sklearn model/pipeline.

    feature_columns:
        Exact columns used while training the model.
    """

    features = extract_ev_features(
        raw_timeseries
    )

    mp_ids = (
        features["MP ID"]
        .copy()
    )

    X_new = (
        features
        .drop(
            columns=["MP ID"]
        )
        .reindex(
            columns=feature_columns
        )
    )

    probabilities = (
        model
        .predict_proba(X_new)[:, 1]
    )

    predictions = (
        model
        .predict(X_new)
        .astype(bool)
    )

    return pd.DataFrame({
        "MP ID":
            mp_ids.values,

        "has_ev_charger_prediction":
            predictions,

        "ev_probability":
            probabilities,
    })