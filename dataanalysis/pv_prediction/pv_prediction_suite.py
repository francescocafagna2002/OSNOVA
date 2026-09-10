import numpy as np
import pandas as pd


def extract_pv_features(raw_timeseries: pd.DataFrame) -> pd.DataFrame:
    df = raw_timeseries.copy()

    df.columns = df.columns.astype(str).str.strip()

    df["MP ID"] = pd.to_numeric(
        df["MP ID"],
        errors="coerce"
    ).astype("Int64")

    df["Datum"] = pd.to_datetime(
        df["Datum"],
        dayfirst=True,
        errors="coerce"
    )

    df = df.dropna(
        subset=["MP ID", "Datum"]
    ).copy()

    expected_time_cols = [
        f"{hour:02d}:{minute:02d}"
        for hour in range(24)
        for minute in [0, 15, 30, 45]
    ]

    actual_time_cols = [
        col for col in expected_time_cols
        if col in df.columns
    ]

    if not actual_time_cols:
        raise ValueError(
            "No 15-minute measurement columns found."
        )

    for col in actual_time_cols:
        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    def hour_from_col(col):
        return int(col.split(":")[0])

    night_cols = [
        c for c in actual_time_cols
        if 0 <= hour_from_col(c) < 6
    ]

    morning_cols = [
        c for c in actual_time_cols
        if 6 <= hour_from_col(c) < 10
    ]

    midday_cols = [
        c for c in actual_time_cols
        if 10 <= hour_from_col(c) < 16
    ]

    afternoon_cols = [
        c for c in actual_time_cols
        if 16 <= hour_from_col(c) < 18
    ]

    evening_cols = [
        c for c in actual_time_cols
        if 18 <= hour_from_col(c) < 23
    ]

    df["daily_mean"] = df[actual_time_cols].mean(axis=1)
    df["daily_std"] = df[actual_time_cols].std(axis=1)
    df["daily_min"] = df[actual_time_cols].min(axis=1)
    df["daily_max"] = df[actual_time_cols].max(axis=1)
    df["daily_median"] = df[actual_time_cols].median(axis=1)

    df["night_mean"] = df[night_cols].mean(axis=1)
    df["morning_mean"] = df[morning_cols].mean(axis=1)
    df["midday_mean"] = df[midday_cols].mean(axis=1)
    df["afternoon_mean"] = df[afternoon_cols].mean(axis=1)
    df["evening_mean"] = df[evening_cols].mean(axis=1)

    epsilon = 1e-6

    df["midday_evening_ratio"] = (
        df["midday_mean"] /
        (df["evening_mean"] + epsilon)
    )

    df["midday_night_ratio"] = (
        df["midday_mean"] /
        (df["night_mean"] + epsilon)
    )

    df["midday_morning_ratio"] = (
        df["midday_mean"] /
        (df["morning_mean"] + epsilon)
    )

    df["evening_minus_midday"] = (
        df["evening_mean"] - df["midday_mean"]
    )

    df["morning_minus_midday"] = (
        df["morning_mean"] - df["midday_mean"]
    )

    df["month"] = df["Datum"].dt.month

    df["season"] = df["month"].map({
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "autumn",
        10: "autumn",
        11: "autumn",
    })

    features = (
        df.groupby("MP ID")
        .agg(
            number_of_days=("Datum", "nunique"),
            overall_mean=("daily_mean", "mean"),
            overall_std=("daily_mean", "std"),
            avg_daily_std=("daily_std", "mean"),
            avg_daily_min=("daily_min", "mean"),
            avg_daily_max=("daily_max", "mean"),
            avg_daily_median=("daily_median", "mean"),
            mean_night=("night_mean", "mean"),
            mean_morning=("morning_mean", "mean"),
            mean_midday=("midday_mean", "mean"),
            mean_afternoon=("afternoon_mean", "mean"),
            mean_evening=("evening_mean", "mean"),
            avg_midday_evening_ratio=(
                "midday_evening_ratio",
                "mean"
            ),
            avg_midday_night_ratio=(
                "midday_night_ratio",
                "mean"
            ),
            avg_midday_morning_ratio=(
                "midday_morning_ratio",
                "mean"
            ),
            avg_evening_minus_midday=(
                "evening_minus_midday",
                "mean"
            ),
            avg_morning_minus_midday=(
                "morning_minus_midday",
                "mean"
            ),
        )
        .reset_index()
    )

    season_midday = (
        df.groupby(["MP ID", "season"])["midday_mean"]
        .mean()
        .unstack()
    )

    for season in ["winter", "spring", "summer", "autumn"]:
        if season not in season_midday.columns:
            season_midday[season] = np.nan

    season_midday = season_midday[
        ["winter", "spring", "summer", "autumn"]
    ]

    season_midday.columns = [
        f"{season}_midday_mean"
        for season in season_midday.columns
    ]

    features = features.merge(
        season_midday.reset_index(),
        on="MP ID",
        how="left"
    )

    season_evening = (
        df.groupby(["MP ID", "season"])["evening_mean"]
        .mean()
        .unstack()
    )

    for season in ["winter", "spring", "summer", "autumn"]:
        if season not in season_evening.columns:
            season_evening[season] = np.nan

    season_evening = season_evening[
        ["winter", "spring", "summer", "autumn"]
    ]

    season_evening.columns = [
        f"{season}_evening_mean"
        for season in season_evening.columns
    ]

    features = features.merge(
        season_evening.reset_index(),
        on="MP ID",
        how="left"
    )

    features["summer_winter_midday_ratio"] = (
        features["summer_midday_mean"] /
        (
            features["winter_midday_mean"]
            + epsilon
        )
    )

    average_profile = (
        df.groupby("MP ID")[actual_time_cols]
        .mean()
        .reset_index()
    )

    average_profile = average_profile.rename(
        columns={
            col: f"profile_{col.replace(':', '_')}"
            for col in actual_time_cols
        }
    )

    features = features.merge(
        average_profile,
        on="MP ID",
        how="left"
    )

    features = features.replace(
        [np.inf, -np.inf],
        np.nan
    )

    return features


def predict_pv(raw_timeseries: pd.DataFrame, model, feature_columns) -> pd.DataFrame:

    features = extract_pv_features(raw_timeseries)

    mp_ids = features["MP ID"].copy()

    X_new = (
        features
        .drop(columns=["MP ID"])
        .reindex(columns=feature_columns)
    )

    probabilities = (model.predict_proba(X_new)[:, 1])

    predictions = (model.predict(X_new).astype(bool))

    return pd.DataFrame({
        "MP ID": mp_ids.values,
        "has_pv_prediction": predictions,
        "pv_probability": probabilities,
    })