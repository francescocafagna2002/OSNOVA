import csv
import gzip
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import patch
from urllib.error import HTTPError
from zipfile import ZipFile

from scripts.fetch_weather import (
    COLUMNS, POSTCODES, VARIABLES, RequestBudget, collect_month, collect_parallel, get_bytes,
    locate_postcodes, main, month_windows, weather_rows,
)


def weather_payload(start, end):
    count = ((end - start).days + 1) * 24
    first = datetime.combine(start, datetime.min.time())
    return {
        "utc_offset_seconds": 0,
        "latitude": 47.5, "longitude": 7.75, "elevation": 280,
        "hourly_units": dict(VARIABLES),
        "hourly": {
            "time": [(first + timedelta(hours=index)).strftime("%Y-%m-%dT%H:%M") for index in range(count)],
            **{variable: [0.0] * count for variable in VARIABLES},
        },
    }


class WeatherTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def test_requested_postcodes(self):
        self.assertEqual(len(POSTCODES), 120)
        self.assertEqual(len(set(POSTCODES)), 120)
        self.assertIn("5001", POSTCODES)
        self.assertIn("8953", POSTCODES)
        self.assertEqual(len(VARIABLES), 10)

    def test_coordinates_and_explicit_aarau_proxy(self):
        text = io.StringIO()
        writer = csv.writer(text, delimiter=";")
        writer.writerows([
            ["PLZ4", "Adressenanteil", "E", "N", "Ortschaftsname"],
            ["5000", "90 %", "8.05", "47.39", "Aarau"],
            ["5000", "10 %", "8.06", "47.38", "Other locality"],
            ["4302", "100 %", "7.71", "47.53", "Augst"],
        ])
        binary = io.BytesIO()
        with ZipFile(binary, "w") as archive:
            archive.writestr("directory.csv", text.getvalue().encode("utf-8-sig"))
        locations = locate_postcodes(binary.getvalue(), ["5001", "4302"])
        self.assertEqual(locations[0]["PLZ"], "5001")
        self.assertEqual(locations[0]["coordinate_plz"], "5000")
        self.assertEqual(locations[0]["longitude"], 8.05)
        self.assertEqual(locations[1]["locality"], "Augst")
        with self.assertRaisesRegex(ValueError, "No coordinates"):
            locate_postcodes(binary.getvalue(), ["9999"])

    def test_month_windows_include_leap_day(self):
        self.assertEqual(list(month_windows(date(2024, 2, 28), date(2024, 3, 2))), [
            (date(2024, 2, 28), date(2024, 2, 29)),
            (date(2024, 3, 1), date(2024, 3, 2)),
        ])

    def test_missing_values_and_zeros_remain_distinct(self):
        start = end = date(2024, 3, 31)
        payload = weather_payload(start, end)
        payload["hourly"]["shortwave_radiation"][0] = None
        payload["hourly"]["sunshine_duration"][0] = None
        payload["hourly"]["sunshine_duration"][12] = 3600.0
        rows = list(weather_rows(payload, "4302", start, end))
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0][:2], ["4302", "2024-03-31T00:00:00Z"])
        self.assertIsNone(rows[0][4])
        self.assertEqual(rows[1][4], 0.0)
        sunshine_index = COLUMNS.index("sunshine_duration")
        self.assertIsNone(rows[0][sunshine_index])
        self.assertEqual(rows[12][sunshine_index], 3600.0)
        self.assertEqual(VARIABLES["sunshine_duration"], "s")
        self.assertEqual(VARIABLES["wind_speed_10m"], "m/s")

    def test_invalid_weather_response_is_rejected(self):
        start = end = date(2023, 1, 1)
        for defect in ("offset", "gap", "unit", "length", "nan"):
            with self.subTest(defect=defect):
                payload = weather_payload(start, end)
                if defect == "offset":
                    payload["utc_offset_seconds"] = 3600
                elif defect == "gap":
                    payload["hourly"]["time"][1] = payload["hourly"]["time"][0]
                elif defect == "unit":
                    payload["hourly_units"]["temperature_2m"] = "F"
                elif defect == "length":
                    payload["hourly"]["cloud_cover"].pop()
                else:
                    payload["hourly"]["temperature_2m"][0] = float("nan")
                with self.assertRaises(ValueError):
                    list(weather_rows(payload, "4302", start, end))

    def test_download_and_resume_and_corrupt_cache(self):
        start = end = date(2023, 1, 1)
        payload = weather_payload(start, end)
        payload["hourly"]["shortwave_radiation"][0] = None
        location = {"PLZ": "4302", "latitude": 47.53, "longitude": 7.71}
        with patch("scripts.fetch_weather.get_bytes", return_value=json.dumps(payload).encode()) as download:
            receipt, cached = collect_month(self.root, location, start, end, None)
            self.assertFalse(cached)
            self.assertGreaterEqual(receipt["timing_seconds"]["api_and_quota"], 0)
            self.assertGreaterEqual(receipt["timing_seconds"]["file_and_checksum"], 0)
            self.assertEqual(receipt["missing_values"]["shortwave_radiation"], 1)
            second, cached = collect_month(self.root, location, start, end, None)
            self.assertTrue(cached)
            self.assertEqual(second, receipt)
            download.assert_called_once()
            self.assertIn("wind_speed_unit=ms", download.call_args.args[0])
            target = self.root / "hourly/4302/2023-01.csv.gz"
            with gzip.open(target, "rt", newline="") as source:
                header, first, second, *remaining = list(csv.reader(source))
            self.assertEqual(header, COLUMNS)
            self.assertEqual(first[4], "")
            self.assertEqual(second[4], "0.0")
            receipt_path = target.with_suffix("").with_suffix(".json")
            old_receipt = json.loads(receipt_path.read_text())
            del old_receipt["timing_seconds"]
            receipt_path.write_text(json.dumps(old_receipt))
            self.assertTrue(collect_month(self.root, location, start, end, None)[1])
            download.assert_called_once()
            target.write_bytes(b"interrupted write")
            self.assertFalse(collect_month(self.root, location, start, end, None)[1])
            self.assertEqual(download.call_count, 2)

    def test_invalid_response_does_not_mark_block_complete(self):
        start = end = date(2023, 1, 1)
        payload = weather_payload(start, end)
        payload["hourly"]["cloud_cover"] = [None] * 24
        location = {"PLZ": "4302", "latitude": 47.53, "longitude": 7.71}
        with patch("scripts.fetch_weather.get_bytes", return_value=json.dumps(payload).encode()):
            with self.assertRaisesRegex(ValueError, "entire variable"):
                collect_month(self.root, location, start, end, None)
        self.assertFalse((self.root / "hourly/4302/2023-01.json").exists())

    def test_budget_survives_restart_and_expires_after_24_hours(self):
        path = self.root / "api_usage.json"
        with patch("scripts.fetch_weather.time.time", return_value=100000), patch("scripts.fetch_weather.time.sleep") as wait:
            RequestBudget(path).reserve(8999)
            with self.assertRaisesRegex(RuntimeError, "24-hour"):
                RequestBudget(path).reserve(2)
            wait.assert_not_called()
        with patch("scripts.fetch_weather.time.time", return_value=200000):
            RequestBudget(path).reserve(3)
        self.assertEqual(len(json.loads(path.read_text())["calls"]), 1)

    def test_request_pacing(self):
        path = self.root / "api_usage.json"
        with patch("scripts.fetch_weather.time.time", return_value=100000), patch("scripts.fetch_weather.time.sleep") as wait:
            RequestBudget(path).reserve(3)
            RequestBudget(path).reserve(3)
            wait.assert_called_once_with(3)

    def test_concurrent_workers_share_pacing_and_persist_every_reservation(self):
        path = self.root / "api_usage.json"
        budget = RequestBudget(path)
        clock = [100000.0]

        def advance(seconds):
            clock[0] += seconds

        with patch("scripts.fetch_weather.time.time", side_effect=lambda: clock[0]), patch("scripts.fetch_weather.time.sleep", side_effect=advance):
            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(budget.reserve, [3] * 8))
        calls = json.loads(path.read_text())["calls"]
        self.assertEqual([call["time"] for call in calls], [100000 + 3 * index for index in range(8)])
        self.assertEqual(sum(call["units"] for call in calls), 24)

    def test_cancellation_during_pacing_does_not_reserve_another_request(self):
        budget = RequestBudget(self.root / "api_usage.json")
        with patch("scripts.fetch_weather.time.time", return_value=100000):
            budget.reserve(3)
            with patch("scripts.fetch_weather.time.sleep", side_effect=lambda seconds: budget.stop()):
                with self.assertRaisesRegex(RuntimeError, "Download stopped"):
                    budget.reserve(3)
        self.assertEqual(len(budget.state["calls"]), 1)

    def test_parallel_blocks_overlap_with_bounded_worker_count(self):
        barrier = Barrier(4)
        lock = Lock()
        active = peak = 0
        start = end = date(2023, 1, 1)
        jobs = [({"PLZ": postcode}, start, end) for postcode in POSTCODES[:8]]

        def collect(output, location, start, end, budget):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            return {"PLZ": location["PLZ"]}, False

        with patch("scripts.fetch_weather.collect_month", side_effect=collect):
            results = list(collect_parallel(self.root, jobs, RequestBudget(self.root / "api_usage.json"), 4))
        self.assertEqual(peak, 4)
        self.assertEqual({receipt["PLZ"] for receipt, cached, elapsed in results}, set(POSTCODES[:8]))

    def test_failed_job_stops_submitting_more_work(self):
        budget = RequestBudget(self.root / "api_usage.json")
        start = end = date(2023, 1, 1)
        jobs = [({"PLZ": postcode}, start, end) for postcode in POSTCODES[:8]]
        with patch("scripts.fetch_weather.collect_month", side_effect=RuntimeError("API failed")) as collect:
            with self.assertRaisesRegex(RuntimeError, "API failed"):
                list(collect_parallel(self.root, jobs, budget, 1))
        collect.assert_called_once()
        self.assertTrue(budget.stopped.is_set())

    def test_cooldowns_cannot_shorten_each_other(self):
        budget = RequestBudget(self.root / "api_usage.json")
        with patch("scripts.fetch_weather.time.time", return_value=100000):
            budget.defer(86400)
            budget.defer(60)
        self.assertEqual(budget.state["not_before"], 186400)

    def test_429_stops_without_retrying_and_saves_cooldown(self):
        budget = RequestBudget(self.root / "api_usage.json")
        error = HTTPError("https://example.test", 429, "Rate limit", {"Retry-After": "120"}, io.BytesIO(b"limit"))
        with patch("scripts.fetch_weather.urlopen", side_effect=error) as download:
            with self.assertRaisesRegex(RuntimeError, "rate limit"):
                get_bytes("https://example.test", budget)
        download.assert_called_once()
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            RequestBudget(budget.path).reserve(1)

    def test_main_receipts_and_configuration_guard(self):
        text = "PLZ4;Adressenanteil;E;N;Ortschaftsname\n4302;100 %;7.71;47.53;Augst\n"
        binary = io.BytesIO()
        with ZipFile(binary, "w") as archive:
            archive.writestr("directory.csv", text)
        start = end = date(2023, 1, 1)
        payload = json.dumps(weather_payload(start, end)).encode()
        arguments = ["--start", str(start), "--end", str(end), "--plz", "4302", "--output", str(self.root)]
        with patch("scripts.fetch_weather.get_bytes", side_effect=[binary.getvalue(), payload]), patch("sys.stdout", io.StringIO()):
            self.assertEqual(main(arguments), 0)
        totals = json.loads((self.root / "_SUCCESS.json").read_text())
        self.assertEqual(totals["rows"], 24)
        with patch("scripts.fetch_weather.get_bytes", side_effect=AssertionError("Must use cache")), patch("sys.stdout", io.StringIO()):
            self.assertEqual(main(arguments), 0)
            self.assertEqual(main([*arguments, "--workers", "1"]), 0)
            self.assertEqual(main(["--start", str(start), "--plz", "4302", "--output", str(self.root)]), 0)
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            main([*arguments, "--end", "2023-01-02"])
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            main([*arguments, "--end", "2027-01-01"])


if __name__ == "__main__":
    unittest.main()