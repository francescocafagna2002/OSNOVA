from pathlib import Path
import argparse
import pandas as pd

from model import model, feature_columns
from pv_prediction_suite import predict_pv


# ------------------------------------------------------------
# Arguments
# ------------------------------------------------------------

parser = argparse.ArgumentParser(
    description="Predict whether an MP ID has PV."
)

parser.add_argument(
    "mp_id",
    type=int,
    help="MP ID to predict"
)

args = parser.parse_args()

mp_id = args.mp_id


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

data_root = Path(
    "../../../store/parquet_data/2026"
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

print(
    f"Looking for MP ID {mp_id} "
    f"in {len(files)} parquet files..."
)


# ------------------------------------------------------------
# Load the full 2026 history for this MP ID
# ------------------------------------------------------------

frames = []

for file in files:
    try:
        df = pd.read_parquet(file)

        if "MP ID" not in df.columns:
            continue

        if "Datum" not in df.columns:
            continue

        df["MP ID"] = pd.to_numeric(
            df["MP ID"],
            errors="coerce"
        ).astype("Int64")

        meter_data = df[
            df["MP ID"] == mp_id
        ].copy()

        if not meter_data.empty:
            frames.append(
                meter_data
            )

    except Exception as e:
        print(
            f"FAILED reading {file}: {e}"
        )


# ------------------------------------------------------------
# Check whether the MP ID exists
# ------------------------------------------------------------

if not frames:
    raise ValueError(
        f"No time-series data found "
        f"for MP ID {mp_id}"
    )


# ------------------------------------------------------------
# Combine all available history
# ------------------------------------------------------------

timeseries = pd.concat(
    frames,
    ignore_index=True
)


print(
    f"Found {len(timeseries)} rows "
    f"for MP ID {mp_id}"
)

if "Datum" in timeseries.columns:

    dates = pd.to_datetime(
        timeseries["Datum"],
        dayfirst=True,
        errors="coerce"
    )

    print(
        "Date range:",
        dates.min(),
        "->",
        dates.max()
    )


# ------------------------------------------------------------
# Predict PV
# ------------------------------------------------------------

prediction = predict_pv(
    raw_timeseries=timeseries,
    model=model,
    feature_columns=feature_columns,
)


# ------------------------------------------------------------
# Extract result
# ------------------------------------------------------------

result = prediction.iloc[0]

has_pv = bool(
    result["has_pv_prediction"]
)

probability = float(
    result["pv_probability"]
)


# ------------------------------------------------------------
# Output
# ------------------------------------------------------------

print()
print("------------------------------")
print("PV PREDICTION")
print("------------------------------")

print(
    f"MP ID:          {mp_id}"
)

print(
    f"Has PV:         {has_pv}"
)

print(
    f"PV probability: {probability:.2%}"
)

print("------------------------------")