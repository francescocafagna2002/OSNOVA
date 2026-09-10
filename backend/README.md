# OSNOVA Backend

Python data processing for the **Energy Fingerprints** challenge — reading the
AEW smart-meter mounts and turning them into features, labels, and model output.

## Requirements

Python 3.10+. Dependencies are declared in [`pyproject.toml`](pyproject.toml)
(`polars`, `pandas`); `scripts/preview_data.py` itself uses only the standard
library, so it runs in a bare Renku session with no install step.

## Layout

```text
backend/
  pyproject.toml       # project metadata and dependencies
  scripts/
    preview_data.py    # print header + first ten records of each CSV in a mount
    fetch_weather.py   # collect hourly weather, with resumable monthly downloads
  tests/
    test_preview_data.py
    test_fetch_weather.py
```

## Preview the data mount

Run from this directory — `scripts` is imported as a top-level package, so the
working directory has to be `backend/`:

```sh
python3 scripts/preview_data.py
```

It searches the current directory and its parents for an `aew-data` /
`aew_data` mount (including under `data/`), then recursively previews every
`.csv` and `.csv.gz`. Pass an explicit path if the mount lives elsewhere:

```sh
python3 scripts/preview_data.py /actual/path/to/aew-data
```

Keep previews in the Renku console. Never commit real customer records or
credentials, and write processing output to the organizer-provided `store`
mount rather than the read-only input mount.

## Hourly weather collection

`scripts/fetch_weather.py` uses only the Python standard library (Python 3.10+).
It downloads Open-Meteo ERA5 hourly weather for the 120 consumption PLZ codes
embedded in the script. It never reads or modifies customer measurements, and
it does not require the Azure SAS URL or a weather API key.

This stage collects weather only. Consumption joins, labels and model-specific
features for PV, EV, batteries or heat pumps are separate downstream tasks.

From the repository root in Renku, run:

```sh
python3 -u backend/scripts/fetch_weather.py --end 2026-07-31 --output /home/renku/work/store/weather_era5
```

The example covers January 2023 through July 2026, matching the displayed input
months. Set `--end` to the last UTC date needed for your measurement intervals.
If omitted, the first run uses the current UTC date minus six days (ERA5 normally
has a five-day publication delay), capped at 2026-12-31. A resumed run keeps its
original end date. `--start` defaults to 2023-01-01. Future/unpublished end dates
are rejected. Local-time joins may need an extra boundary date; confirm the
meter time convention before fixing the final weather date range.

For a short initial test, use a separate output directory:

```sh
python3 -u backend/scripts/fetch_weather.py --start 2023-06-01 --end 2023-06-02 --plz 4302 5001 --output /home/renku/work/store/weather_smoke
```

### Output and resuming

The output is a partitioned table: `hourly/<PLZ>/<YYYY-MM>.csv.gz`. Each row has
the following columns; units are not embedded in the numeric values:

| Column | Units | Time meaning |
| --- | --- | --- |
| `PLZ` | string identifier | Postal code requested |
| `timestamp_utc` | ISO 8601 ending in `Z` | UTC timestamp |
| `temperature_2m` | degrees Celsius | Instant at timestamp |
| `cloud_cover` | percent | Instant at timestamp |
| `shortwave_radiation` | W/m2 | Mean global horizontal radiation over preceding hour |
| `direct_radiation` | W/m2 | Mean direct horizontal radiation over preceding hour |
| `diffuse_radiation` | W/m2 | Mean diffuse radiation over preceding hour |
| `sunshine_duration` | seconds | Sunshine duration over preceding hour |
| `relative_humidity_2m` | percent | Instant at timestamp |
| `precipitation` | mm | Total precipitation, including snow water equivalent, over preceding hour |
| `snowfall` | cm | Snowfall over preceding hour |
| `wind_speed_10m` | m/s | Instant at timestamp |

`PLZ, timestamp_utc` is the weather table's unique join key. Keep timestamps in
UTC and preserve the distinction between instantaneous values and preceding-hour
aggregates. Before joining consumption, confirm its timestamp and daylight-saving
conventions; do not blindly round 15-minute interval-end labels down to the hour.

Empty fields remain missing; real zeros remain zero. Each block is checked for
units, ordered continuous UTC hours, value types and expected row count. An
entirely unavailable variable causes a failure rather than a successful empty
download. Other missing values are preserved and counted in the receipts.

- `plz_coordinates.csv` records the coordinate and selection method per PLZ.
- `swisstopo_postcodes_4326.csv.zip` pins the downloaded geographic reference.
- `metadata.json` records dates, variables, model, units, attribution and time semantics.
- Each monthly `.json` receipt records the request, returned grid coordinates,
  missing-value counts and SHA-256 of the completed `.csv.gz` file.
- `_SUCCESS.json` appears only when every requested PLZ/month has completed.
- `api_usage.json` persists conservative request accounting and API cooldowns.

Rerun the exact command to resume. A block with a valid matching receipt and
checksum is skipped; partial/corrupted blocks are fetched again. Do not treat
the output as complete without `_SUCCESS.json`. Use only one running collector
per output directory. Changing dates, variables or PLZ selection requires a
different output directory; do not combine overlapping runs into one table
without checking for duplicate keys.

API requests are sequential, paced at roughly one counted call unit per second,
and stopped before exceeding a local rolling budget of 9,000 units in 24 hours.
A month counts conservatively as up to three units, not one request. The full
multi-year collection can therefore require more than one day of free quota.
HTTP 429 stops the run and saves the server cooldown; transient network/server
errors get at most three attempts. After the indicated cooldown, resume with the
same command. Limits apply to the shared public IP, so other Renku users can
exhaust the quota earlier. Do not delete accounting or rotate directories to
bypass rate limits. A changed directory is for a changed dataset configuration,
not a separate API quota.

### Spatial and usage limitations

ERA5 is selected explicitly for a consistent source throughout 2023-2026; it is
reanalysis, not a weather station at each building. Resolution is approximately
25 km, so nearby PLZ codes can share a weather grid cell. Coordinates come from
the swisstopo locality entry with the largest address share. Postal code `5001`
is explicitly mapped to the representative coordinate of Aarau `5000`, while
retaining `5001` as the output key. These are regional proxies, not roof-level
irradiance or historical address reconstructions.

The free Open-Meteo service is restricted to non-commercial use, including
eligible evaluation/prototyping. Check the terms before commercial research or
product use. Weather data requires attribution under CC BY 4.0:

- [Open-Meteo archive documentation](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo terms](https://open-meteo.com/en/terms)
- [Open-Meteo pricing and counted requests](https://open-meteo.com/en/pricing)
- [swisstopo postal locality reference](https://data.geo.admin.ch/browser/index.html#/collections/ch.swisstopo-vd.ortschaftenverzeichnis_plz)

## Tests

Synthetic-data tests, standard library only:

```sh
python3 -m unittest discover -s tests
```
