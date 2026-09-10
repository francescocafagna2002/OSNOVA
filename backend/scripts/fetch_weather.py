"""Collect hourly weather for the challenge postal codes without meter data."""

import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import math
import sys
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from itertools import islice
from pathlib import Path
from threading import Event, Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile


POSTCODES = """
4302 4303 4304 4310 4312 4313 4314 4315 4316 4317
4322 4323 4324 4325 4332 4333 4334 4422 4468 4469
4665 4805 4813 4814 5000 5001 5026 5027 5028 5044
5046 5054 5070 5072 5073 5074 5075 5076 5077 5078
5079 5105 5106 5107 5108 5112 5113 5213 5223 5225
5235 5236 5237 5244 5272 5301 5304 5305 5306 5312
5313 5314 5315 5316 5322 5324 5325 5330 5332 5334
5425 5426 5443 5445 5452 5454 5462 5464 5467 5504
5505 5506 5507 5522 5600 5604 5605 5607 5608 5614
5615 5616 5617 5618 5619 5620 5621 5622 5623 5625
5630 5643 5705 5706 5707 5724 5725 5726 5727 5728
5733 5735 5736 5737 5745 8918 8953 8962 8964 8967
""".split()
VARIABLES = {
    "temperature_2m": "\u00b0C",
    "cloud_cover": "%",
    "shortwave_radiation": "W/m\u00b2",
    "direct_radiation": "W/m\u00b2",
    "diffuse_radiation": "W/m\u00b2",
    "sunshine_duration": "s",
    "relative_humidity_2m": "%",
    "precipitation": "mm",
    "snowfall": "cm",
    "wind_speed_10m": "m/s",
}
COORDINATES_URL = (
    "https://data.geo.admin.ch/ch.swisstopo-vd.ortschaftenverzeichnis_plz/"
    "ortschaftenverzeichnis_plz/ortschaftenverzeichnis_plz_4326.csv.zip"
)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
MODEL = "era5"
COLUMNS = ["PLZ", "timestamp_utc", *VARIABLES]


def write_json(path, value):
    with path.open("w", encoding="utf-8") as destination:
        json.dump(value, destination, indent=2, sort_keys=True, allow_nan=False)
        destination.write("\n")


def file_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RequestBudget:
    def __init__(self, path):
        self.path = path
        self.state = json.loads(path.read_text()) if path.exists() else {"calls": [], "not_before": 0}
        self.lock = Lock()
        self.stopped = Event()

    def reserve(self, units):
        with self.lock:
            if self.stopped.is_set():
                raise RuntimeError("Download stopped; no new API requests will start.")
            now = time.time()
            calls = [call for call in self.state["calls"] if call["time"] > now - 86400]
            if now < self.state["not_before"]:
                raise RuntimeError("API cooldown is active. Retry later with the same output directory.")
            if sum(call["units"] for call in calls) + units > 9000:
                raise RuntimeError("Rolling 24-hour API budget reached. Retry tomorrow with the same command.")
            if calls:
                time.sleep(max(0, calls[-1]["time"] + calls[-1]["units"] - now))
            if self.stopped.is_set():
                raise RuntimeError("Download stopped; no new API requests will start.")
            calls.append({"time": time.time(), "units": units})
            self.state["calls"] = calls
            write_json(self.path, self.state)

    def defer(self, seconds):
        self.stop()
        with self.lock:
            self.state["not_before"] = max(self.state["not_before"], time.time() + seconds)
            write_json(self.path, self.state)

    def stop(self):
        self.stopped.set()


def get_bytes(url, budget=None, units=1):
    for attempt in range(3):
        if budget is not None:
            budget.reserve(units)
        try:
            request = Request(url, headers={"User-Agent": "OSNOVA-weather/1.0"})
            with urlopen(request, timeout=90) as response:
                return response.read()
        except HTTPError as error:
            with error:
                reason = error.read(4096).decode("utf-8", errors="replace")
            if error.code == 429:
                retry_after = error.headers.get("Retry-After", "86400")
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
                if budget is not None:
                    budget.defer(max(60, delay))
                raise RuntimeError(f"API rate limit: {reason}. Saved blocks are retained.") from error
            if error.code not in (500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"HTTP {error.code}: {reason}") from error
        except (URLError, TimeoutError) as error:
            if attempt == 2:
                raise RuntimeError(f"Download failed: {error}") from error
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Download failed")


def locate_postcodes(payload, postcodes):
    candidates = {}
    with ZipFile(io.BytesIO(payload)) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Expected exactly one CSV in the swisstopo archive")
        with archive.open(members[0]) as source:
            reader = csv.DictReader(io.TextIOWrapper(source, encoding="utf-8-sig"), delimiter=";")
            for row in reader:
                postcode = row["PLZ4"].strip()
                share = float(row["Adressenanteil"].removesuffix("%").strip())
                if postcode not in candidates or share > candidates[postcode][0]:
                    candidates[postcode] = (share, row)
    locations = []
    for postcode in postcodes:
        coordinate_postcode = "5000" if postcode == "5001" else postcode
        if coordinate_postcode not in candidates:
            raise ValueError(f"No coordinates found for PLZ {postcode}")
        row = candidates[coordinate_postcode][1]
        longitude, latitude = float(row["E"]), float(row["N"])
        if not (5 <= longitude <= 11 and 45 <= latitude <= 48):
            raise ValueError(f"Coordinates for PLZ {postcode} are not Swiss WGS84 coordinates")
        locations.append({
            "PLZ": postcode,
            "latitude": latitude,
            "longitude": longitude,
            "locality": row["Ortschaftsname"],
            "coordinate_plz": coordinate_postcode,
            "coordinate_method": (
                "Aarau 5000 proxy for postal code 5001"
                if postcode == "5001" else "swisstopo locality with largest address share"
            ),
        })
    return locations


def month_windows(start, end):
    while start <= end:
        last = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
        stop = min(last, end)
        yield start, stop
        start = stop + timedelta(days=1)


def weather_rows(payload, postcode, start, end):
    if payload.get("error"):
        raise ValueError(payload.get("reason", "Weather API returned an error"))
    if payload.get("utc_offset_seconds") != 0:
        raise ValueError("Expected UTC weather timestamps")
    hourly = payload["hourly"]
    count = ((end - start).days + 1) * 24
    if len(hourly["time"]) != count:
        raise ValueError(f"Expected {count} hourly timestamps for PLZ {postcode}")
    for variable, unit in VARIABLES.items():
        if len(hourly[variable]) != count or payload["hourly_units"][variable] != unit:
            raise ValueError(f"Unexpected length or units for {variable}")
    first = datetime.combine(start, datetime.min.time(), timezone.utc)
    for index, timestamp in enumerate(hourly["time"]):
        expected = (first + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M")
        if timestamp != expected:
            raise ValueError(f"Missing, duplicate or unordered timestamp: {timestamp}")
        values = [hourly[variable][index] for variable in VARIABLES]
        if any(value is not None and (type(value) not in (int, float) or not math.isfinite(value)) for value in values):
            raise ValueError(f"Invalid weather value at {timestamp}")
        yield [postcode, timestamp + ":00Z", *values]


def collect_month(output, location, start, end, budget):
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(VARIABLES),
        "models": MODEL,
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    postcode = location["PLZ"]
    folder = output / "hourly" / postcode
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{start:%Y-%m}.csv.gz"
    receipt_path = folder / f"{start:%Y-%m}.json"
    expected_rows = ((end - start).days + 1) * 24
    if target.is_file() and receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text())
            if (receipt["request"] == params and receipt["PLZ"] == postcode
                    and receipt["rows"] == expected_rows and receipt["sha256"] == file_digest(target)):
                return receipt, True
        except (ValueError, KeyError):
            pass
    api_started = time.perf_counter()
    payload = json.loads(get_bytes(
        ARCHIVE_URL + "?" + urlencode(params), budget,
        units=math.ceil(((end - start).days + 1) / 14) * max(1, math.ceil(len(VARIABLES) / 10)),
    ))
    api_seconds = time.perf_counter() - api_started
    rows = list(weather_rows(payload, postcode, start, end))
    receipt = {
        "PLZ": postcode, "request": params, "rows": len(rows),
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "grid_latitude": payload["latitude"], "grid_longitude": payload["longitude"],
        "elevation_m": payload["elevation"],
        "missing_values": {
            variable: sum(row[index + 2] is None for row in rows)
            for index, variable in enumerate(VARIABLES)
        },
    }
    if any(count == len(rows) for count in receipt["missing_values"].values()):
        raise ValueError(f"An entire variable is missing for PLZ {postcode}, {start:%Y-%m}")
    file_started = time.perf_counter()
    receipt_path.unlink(missing_ok=True)
    with gzip.open(target, "wt", encoding="utf-8", newline="", compresslevel=6) as destination:
        writer = csv.writer(destination, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    receipt["sha256"] = file_digest(target)
    receipt["timing_seconds"] = {
        "api_and_quota": round(api_seconds, 3),
        "file_and_checksum": round(time.perf_counter() - file_started, 3),
    }
    write_json(receipt_path, receipt)
    return receipt, False


def collect_job(output, job, budget):
    started = time.perf_counter()
    location, start, end = job
    receipt, cached = collect_month(output, location, start, end, budget)
    return receipt, cached, time.perf_counter() - started


def collect_parallel(output, jobs, budget, workers):
    remaining = iter(jobs)
    executor = ThreadPoolExecutor(max_workers=workers)
    pending = set()
    try:
        for job in islice(remaining, workers):
            pending.add(executor.submit(collect_job, output, job, budget))
        while pending:
            finished, pending = wait(pending, return_when=FIRST_COMPLETED)
            results = [future.result() for future in finished]
            for result in results:
                yield result
            for job in islice(remaining, len(finished)):
                pending.add(executor.submit(collect_job, output, job, budget))
    finally:
        budget.stop()
        for future in pending:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)


def default_output():
    renku_store = Path("/home/renku/work/store")
    store = renku_store if renku_store.is_dir() else Path(__file__).resolve().parents[2] / "store"
    return store / "weather_era5"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2023, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat,
                        help="Inclusive UTC date; defaults to today minus six days, capped at 2026-12-31")
    parser.add_argument("--output", type=Path, default=default_output())
    parser.add_argument("--plz", nargs="+", default=POSTCODES, choices=POSTCODES,
                        help="Optional subset for a short smoke test")
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=4,
                        help="Concurrent blocks (default: 4); all workers share one API quota")
    args = parser.parse_args(argv)
    output = args.output.expanduser().resolve()
    metadata_path = output / "metadata.json"
    previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else None
    latest = min(date(2026, 12, 31), datetime.now(timezone.utc).date() - timedelta(days=6))
    end = args.end or (date.fromisoformat(previous["end_date"]) if previous else latest)
    if not args.start <= end <= latest:
        parser.error(f"Require start <= end <= {latest} (ERA5 publication delay)")
    config = {
        "schema_version": 1, "start_date": args.start.isoformat(), "end_date": end.isoformat(),
        "postcodes": sorted(set(args.plz)), "model": MODEL, "variables": VARIABLES,
        "timezone": "UTC", "columns": COLUMNS,
    }
    if previous is not None and any(previous.get(key) != value for key, value in config.items()):
        parser.error("This directory has a different configuration. Use its original arguments or a new directory.")
    output.mkdir(parents=True, exist_ok=True)
    archive_path = output / "swisstopo_postcodes_4326.csv.zip"
    if previous is not None:
        if file_digest(archive_path) != previous["coordinates_sha256"]:
            raise ValueError("Cached coordinate source changed; refusing to mix coordinate versions")
    if archive_path.exists():
        archive = archive_path.read_bytes()
    else:
        archive = get_bytes(COORDINATES_URL)
        locate_postcodes(archive, config["postcodes"])
        archive_path.write_bytes(archive)
    locations = locate_postcodes(archive, config["postcodes"])
    with (output / "plz_coordinates.csv").open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(locations[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(locations)
    metadata = previous or {
        **config, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "coordinates_url": COORDINATES_URL, "coordinates_sha256": file_digest(archive_path),
        "weather_url": ARCHIVE_URL,
        "attribution": ["Weather: Open-Meteo.com (CC BY 4.0), ECMWF ERA5 / Copernicus Climate Change Service",
                        "Postal locality coordinates: Federal Office of Topography swisstopo"],
        "documentation": "https://open-meteo.com/en/docs/historical-weather-api",
        "terms": "https://open-meteo.com/en/terms",
        "temporal_semantics": {
            "temperature_2m": "instant at timestamp_utc", "cloud_cover": "instant at timestamp_utc",
            "shortwave_radiation": "mean W/m2 over preceding hour, ending at timestamp_utc",
            "direct_radiation": "mean horizontal W/m2 over preceding hour, ending at timestamp_utc",
            "diffuse_radiation": "mean W/m2 over preceding hour, ending at timestamp_utc",
            "sunshine_duration": "seconds of sunshine in preceding hour, ending at timestamp_utc",
            "relative_humidity_2m": "instant at timestamp_utc",
            "precipitation": "total precipitation water equivalent in mm over preceding hour",
            "snowfall": "snowfall in cm over preceding hour",
            "wind_speed_10m": "instant at timestamp_utc, in m/s",
        },
        "missing_values": "Empty CSV fields are missing, not zero; no interpolation or filling",
        "spatial_caveat": "ERA5 is approximately 25 km; PLZ coordinates are locality proxies, not building locations",
    }
    write_json(metadata_path, metadata)
    success_path = output / "_SUCCESS.json"
    success_path.unlink(missing_ok=True)
    jobs = [(location, start, stop) for start, stop in month_windows(args.start, end) for location in locations]
    budget = RequestBudget(output / "api_usage.json")
    totals = {"rows": 0, "blocks": len(jobs), "missing_values": dict.fromkeys(VARIABLES, 0)}
    workers = min(args.workers, len(jobs))
    print(f"PLZ: {len(locations)} | UTC: {args.start} through {end} | Model: {MODEL}", flush=True)
    print(f"Output: {output}\nWorkers: {workers}; shared quota control; rerun to resume.", flush=True)
    for index, (receipt, cached, elapsed) in enumerate(collect_parallel(output, jobs, budget, workers), 1):
        totals["rows"] += receipt["rows"]
        for variable in VARIABLES:
            totals["missing_values"][variable] += receipt["missing_values"][variable]
        details = ""
        if not cached:
            timing = receipt["timing_seconds"]
            details = f" api+quota={timing['api_and_quota']:.1f}s file+checksum={timing['file_and_checksum']:.1f}s"
        print(f"[{index}/{len(jobs)}] {'CACHED' if cached else 'SAVED'} PLZ={receipt['PLZ']} "
              f"{receipt['request']['start_date'][:7]} hours={receipt['rows']} total={elapsed:.1f}s{details}", flush=True)
    expected_rows = ((end - args.start).days + 1) * 24 * len(locations)
    if totals["rows"] != expected_rows:
        raise ValueError("Unexpected total row count")
    write_json(success_path, {**totals, "completed_at_utc": datetime.now(timezone.utc).isoformat()})
    print(f"DONE: {totals['rows']} rows. Missing values: {totals['missing_values']}. Output: {output}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        print(f"STOP: {error}\nCompleted blocks are retained. Rerun the same command to resume.", file=sys.stderr)
        sys.exit(1)