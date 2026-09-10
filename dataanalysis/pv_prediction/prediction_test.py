from pathlib import Path
import pandas as pd

from model import model, feature_columns
from pv_prediction_suite import predict_pv


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

data_root = Path("../../../store/parquet_data/2026")

output_file = Path(
    "../../../store/parquet_data/pv_predictions_2026_sample_10.parquet"
)


# ------------------------------------------------------------
# Find all parquet files
# ------------------------------------------------------------

files = sorted(
    data_root.rglob("*.parquet")
)

if not files:
    raise ValueError(
        "No parquet files found in the 2026 folder."
    )

print(f"Found {len(files)} parquet files")


# ------------------------------------------------------------
# Pick 10 MP IDs from the first file
# ------------------------------------------------------------

first_file = files[0]

print()
print("Using first file:")
print(first_file)

first_df = pd.read_parquet(
    first_file,
    columns=["MP ID"]
)

first_df["MP ID"] = pd.to_numeric(
    first_df["MP ID"],
    errors="coerce"
).astype("Int64")

sample_mp_ids = (
    first_df["MP ID"]
    .dropna()
    .drop_duplicates()
    .sample(
        n=10,
        #random_state=42
    )
    .tolist()
)

if not sample_mp_ids:
    raise ValueError(
        "No valid MP IDs found in the first parquet file."
    )

print()
print("Selected MP IDs:")
print(sample_mp_ids)


# ------------------------------------------------------------
# Load full 2026 history for those 10 MP IDs
# ------------------------------------------------------------

frames = []

for file in files:
    try:
        df = pd.read_parquet(file)

        if "MP ID" not in df.columns:
            print(f"SKIPPED (no MP ID): {file}")
            continue

        if "Datum" not in df.columns:
            print(f"SKIPPED (no Datum): {file}")
            continue

        df["MP ID"] = pd.to_numeric(
            df["MP ID"],
            errors="coerce"
        ).astype("Int64")

        # Keep only the selected 10 MP IDs
        df = df[
            df["MP ID"].isin(sample_mp_ids)
        ].copy()

        if not df.empty:
            frames.append(df)

            print(
                f"Loaded matching rows from: {file} "
                f"({len(df)} rows)"
            )

    except Exception as e:
        print(f"FAILED: {file}")
        print(e)


if not frames:
    raise ValueError(
        "No time-series data found for the selected MP IDs."
    )


# ------------------------------------------------------------
# Combine all their 2026 time series
# ------------------------------------------------------------

sample_timeseries = pd.concat(
    frames,
    ignore_index=True
)

print()
print(
    "Total rows loaded:",
    len(sample_timeseries)
)

print(
    "Unique MP IDs loaded:",
    sample_timeseries["MP ID"].nunique()
)

print()
print("Rows per MP ID:")

print(
    sample_timeseries
    .groupby("MP ID")
    .size()
)


# ------------------------------------------------------------
# Run predictions
# ------------------------------------------------------------

predictions = predict_pv(
    raw_timeseries=sample_timeseries,
    model=model,
    feature_columns=feature_columns,
)


# ------------------------------------------------------------
# Sort results
# ------------------------------------------------------------

predictions = predictions.sort_values(
    "pv_probability",
    ascending=False
).reset_index(drop=True)


# ------------------------------------------------------------
# Show predictions
# ------------------------------------------------------------

print()
print("PV predictions:")

print(predictions)


# ------------------------------------------------------------
# Save results
# ------------------------------------------------------------

predictions.to_parquet(
    output_file,
    engine="pyarrow",
    compression="snappy",
    index=False,
)

print()
print(
    f"Saved predictions to: {output_file}"
)