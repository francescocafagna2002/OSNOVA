from pathlib import Path
import json
import time
import requests
import pandas as pd


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# File with Aargau locations:
# columns required:
# location_id, municipality, ortschaft, plz, latitude, longitude
LOCATIONS_FILE = BASE_DIR / "locations_ag.csv"

# Raw Open-Meteo responses
RAW_DIR = BASE_DIR / "raw" / "openmeteo"

# Processed Parquet files
PARQUET_DIR = BASE_DIR / "parquet"

START_DATE = "2023-01-01"
END_DATE = "2026-07-31"

TIMEZONE = "Europe/Zurich"

# Open-Meteo Historical Forecast API
API_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# How many locations per API request
BATCH_SIZE = 10

# Pause between requests
SLEEP_SECONDS = 1.0


# ============================================================
# WEATHER VARIABLES
# ============================================================

# Native 15-minute variables
MINUTELY_15_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",

    "precipitation",
    "rain",
    "snowfall",

    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",

    "visibility",
    "cape",
    "weather_code",

    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "direct_normal_irradiance",

    "global_tilted_irradiance",
]


# Hourly variables that are useful but are NOT native 15-min fields
HOURLY_VARIABLES = [
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "snow_depth",
    "sunshine_duration",
    "is_day",
]


# ============================================================
# HELPERS
# ============================================================

def load_locations():
    if not LOCATIONS_FILE.exists():
        raise FileNotFoundError(
            f"\nLocation file not found:\n{LOCATIONS_FILE}\n\n"
            "Create locations_ag.csv first."
        )

    df = pd.read_csv(LOCATIONS_FILE)

    required = [
        "location_id",
        "municipality",
        "ortschaft",
        "plz",
        "latitude",
        "longitude",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing columns in {LOCATIONS_FILE}:\n{missing}\n\n"
            f"Required columns:\n{required}"
        )

    df = df.dropna(subset=["latitude", "longitude"]).copy()

    df["latitude"] = pd.to_numeric(df["latitude"])
    df["longitude"] = pd.to_numeric(df["longitude"])

    return df


def chunks(df, size):
    for start in range(0, len(df), size):
        yield df.iloc[start:start + size]


def build_params(batch):
    return {
        "latitude": ",".join(
            str(round(float(x), 6))
            for x in batch["latitude"]
        ),

        "longitude": ",".join(
            str(round(float(x), 6))
            for x in batch["longitude"]
        ),

        "start_date": START_DATE,
        "end_date": END_DATE,

        "minutely_15": ",".join(MINUTELY_15_VARIABLES),

        "hourly": ",".join(HOURLY_VARIABLES),

        "timezone": TIMEZONE,

        "models": "best_match",
    }


def request_openmeteo(batch):
    params = build_params(batch)

    print("\nRequesting Open-Meteo...")
    print(
        f"Locations: {len(batch)} | "
        f"{START_DATE} → {END_DATE}"
    )

    response = requests.get(
        API_URL,
        params=params,
        timeout=180,
    )

    if response.status_code != 200:
        print("\nOpen-Meteo ERROR:")
        print(response.text[:3000])

        response.raise_for_status()

    return response.json()


def save_raw_json(data, batch_number):
    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    year_dir = RAW_DIR / f"{START_DATE[:4]}-{END_DATE[:4]}"
    year_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        year_dir /
        f"batch_{batch_number:03d}.json"
    )

    with open(
        filename,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
        )

    print(f"RAW JSON saved: {filename}")

    return filename


# ============================================================
# PARSE OPEN-METEO RESPONSE
# ============================================================

def parse_response(data, batch):
    rows = []

    # Open-Meteo returns:
    # - dict when one location
    # - list when multiple locations

    if isinstance(data, dict):
        locations_data = [data]
    else:
        locations_data = data

    if len(locations_data) != len(batch):
        print(
            f"WARNING: "
            f"{len(locations_data)} responses returned "
            f"for {len(batch)} locations."
        )

    for idx, location_data in enumerate(locations_data):

        if idx >= len(batch):
            break

        location = batch.iloc[idx]

        location_id = location["location_id"]

        # ----------------------------------------------------
        # 15 MINUTE DATA
        # ----------------------------------------------------

        minutely = location_data.get("minutely_15")

        if minutely:

            times = minutely.get("time", [])

            for i, timestamp in enumerate(times):

                row = {
                    "timestamp": timestamp,

                    "location_id": location_id,
                    "municipality": location["municipality"],
                    "ortschaft": location["ortschaft"],
                    "plz": location["plz"],

                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                }

                for variable in MINUTELY_15_VARIABLES:

                    values = minutely.get(variable)

                    if values is not None and i < len(values):
                        row[variable] = values[i]
                    else:
                        row[variable] = None

                rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# SAVE PARQUET
# ============================================================

def save_parquet(df):

    if df.empty:
        print("No data to save.")
        return

    PARQUET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
    )

    df = df.dropna(
        subset=["timestamp"]
    )

    # Keep requested period only
    start = pd.Timestamp(
        START_DATE,
        tz=TIMEZONE,
    )

    end = (
        pd.Timestamp(END_DATE, tz=TIMEZONE)
        + pd.Timedelta(days=1)
        - pd.Timedelta(seconds=1)
    )

    # Convert if timestamps are timezone-aware
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = (
            df["timestamp"]
            .dt.tz_localize(TIMEZONE)
        )

    df = df[
        (df["timestamp"] >= start)
        &
        (df["timestamp"] <= end)
    ]

    df = df.sort_values(
        [
            "location_id",
            "timestamp",
        ]
    )

    df = df.drop_duplicates(
        subset=[
            "location_id",
            "timestamp",
        ]
    )

    # --------------------------------------------------------
    # Save one Parquet per year
    # --------------------------------------------------------

    for year, year_df in df.groupby(
        df["timestamp"].dt.year
    ):

        output = (
            PARQUET_DIR /
            f"weather_{year}.parquet"
        )

        year_df.to_parquet(
            output,
            index=False,
            engine="pyarrow",
            compression="zstd",
        )

        print(
            f"\nPARQUET saved:"
            f"\n{output}"
            f"\nRows: {len(year_df):,}"
            f"\nLocations: "
            f"{year_df['location_id'].nunique()}"
        )


# ============================================================
# MAIN DOWNLOAD
# ============================================================

def main():

    print("=" * 60)
    print("AARGAU OPEN-METEO WEATHER DOWNLOADER")
    print("=" * 60)

    print(f"\nProject directory:")
    print(BASE_DIR)

    print(f"\nDate range:")
    print(f"{START_DATE} → {END_DATE}")

    # --------------------------------------------------------
    # Load locations
    # --------------------------------------------------------

    locations = load_locations()

    print(
        f"\nLocations loaded: "
        f"{len(locations)}"
    )

    print(
        f"Unique municipalities: "
        f"{locations['municipality'].nunique()}"
    )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    all_data = []

    total_batches = (
        (len(locations) + BATCH_SIZE - 1)
        // BATCH_SIZE
    )

    for batch_number, batch in enumerate(
        chunks(locations, BATCH_SIZE),
        start=1,
    ):

        raw_file = (
            RAW_DIR
            / f"{START_DATE[:4]}-{END_DATE[:4]}"
            / f"batch_{batch_number:03d}.json"
        )

        # ----------------------------------------------------
        # RESUME SUPPORT
        # ----------------------------------------------------

        if raw_file.exists():

            print(
                f"\n[{batch_number}/{total_batches}] "
                f"RAW already exists."
            )

            print(
                f"Skipping download: "
                f"{raw_file}"
            )

            with open(
                raw_file,
                "r",
                encoding="utf-8",
            ) as f:
                data = json.load(f)

        else:

            print(
                f"\n[{batch_number}/{total_batches}]"
            )

            data = request_openmeteo(batch)

            save_raw_json(
                data,
                batch_number,
            )

            time.sleep(
                SLEEP_SECONDS
            )

        # ----------------------------------------------------
        # Parse
        # ----------------------------------------------------

        parsed = parse_response(
            data,
            batch,
        )

        print(
            f"Rows parsed: "
            f"{len(parsed):,}"
        )

        if not parsed.empty:
            all_data.append(parsed)

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    if not all_data:
        raise RuntimeError(
            "No weather data was downloaded."
        )

    print("\nCombining data...")

    final_df = pd.concat(
        all_data,
        ignore_index=True,
    )

    print(
        f"Total rows: "
        f"{len(final_df):,}"
    )

    print(
        f"Locations: "
        f"{final_df['location_id'].nunique()}"
    )

    # --------------------------------------------------------
    # Save Parquet
    # --------------------------------------------------------

    save_parquet(
        final_df
    )

    print("\n" + "=" * 60)
    print("DONE")
    print("=" * 60)

    print(
        f"\nRAW:"
        f"\n{RAW_DIR}"
    )

    print(
        f"\nPARQUET:"
        f"\n{PARQUET_DIR}"
    )


if __name__ == "__main__":
    main()