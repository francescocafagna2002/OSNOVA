"""End-to-end test of the feature extraction pipeline against synthetic input.

There is no real AEW data on this machine (see ``backend/CLAUDE.md``), so this
runs ``scripts/make_synth_fixture.py`` in a tmp dir first — small, but shaped
exactly like the real files — and checks:

  * the pipeline runs without error and produces the documented schema;
  * one row per building, and the injected devices move the relevant
    features in the expected direction (PV -> negative solar correlation,
    heat pump -> negative temperature correlation, battery -> more near-zero
    intervals, EV -> nonzero candidate sessions);
  * ``--limit-buildings`` actually limits the output;
  * a duplicate raw row and two unmapped MP IDs (both injected by the
    fixture) are handled rather than crashing the run.
"""

import datetime as dt
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import polars as pl

from feature_pipeline.config import PathsConfig, PipelineConfig
from feature_pipeline.pipeline import FINAL_COLUMNS, run_pipeline
from scripts.make_synth_fixture import generate


class FeaturePipelineSynthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.input_dir = root / "input"
        cls.buildings = generate(
            cls.input_dir,
            n_buildings=40,
            days=120,
            start=dt.date(2024, 1, 1),
            seed=7,
            quiet=True,
        )
        cls.truth = {b["gp_nr"]: b for b in cls.buildings}

        paths = PathsConfig(
            raw_consumption_dir=cls.input_dir,
            mp_mapping_file=cls.input_dir / "mpid_zähler_mapping.csv",
            zaehler_gp_file=cls.input_dir / "Zähler-GP.csv",
            labels_file=cls.input_dir / "HackDays2026 - GIGI.csv",
            weather_dir=cls.input_dir / "weather",
            output_dir=root / "output",
            intermediate_dir=root / "output" / "intermediate",
        )
        cls.cfg = PipelineConfig(paths=paths)
        cls.report = run_pipeline(cls.cfg)
        cls.df = pl.read_parquet(paths.feature_dataset_path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_schema_is_exactly_the_documented_columns(self):
        from osnova.io.store import FEATURE_KEYS

        self.assertEqual(self.df.columns, FINAL_COLUMNS)
        self.assertEqual(self.df.select(FEATURE_KEYS.names()).schema, FEATURE_KEYS)
        self.assertEqual(self.df.schema["gp_nr"], pl.Int64)
        self.assertEqual(self.df.schema["plz"], pl.String)
        self.assertEqual(self.df.schema["num_mp_ids"], pl.Int32)
        self.assertTrue(self.df["gp_nr"].is_between(100000, 999999).all())
        for name in ("label_pv", "label_ev", "label_heatpump", "label_battery"):
            self.assertTrue(self.df[name].drop_nulls().is_in([0, 1]).all())
            self.assertEqual(self.df.schema[name], pl.Int8)
        for name, dtype in self.df.schema.items():
            if name not in {*FEATURE_KEYS.names(), "num_mp_ids"} and not name.startswith("label_"):
                self.assertTrue(dtype.is_float(), name)
        self.assertIn("n_valid_days", self.df.columns)
        self.assertTrue(self.df["n_valid_days"].is_between(0, 120).all())

    def test_one_row_per_building_actually_present_in_consumption(self):
        self.assertEqual(self.df.height, len(self.buildings))
        self.assertEqual(set(self.df.get_column("gp_nr").to_list()), set(self.truth))

    def test_audit_counts_unmapped_and_multi_mp(self):
        self.assertEqual(self.report.number_of_unmapped_mp_ids, 2)
        expected_multi_mp = sum(1 for b in self.buildings if len(b["mp_ids"]) > 1)
        self.assertEqual(self.report.number_of_multi_mp_buildings, expected_multi_mp)
        self.assertGreater(self.report.number_of_processed_buildings, 0)

    def _mean_for_profile(self, column: str, profile: str) -> float:
        gp_nrs = [gp for gp, b in self.truth.items() if b["profile"] == profile]
        vals = self.df.filter(pl.col("gp_nr").is_in(gp_nrs)).get_column(column).drop_nulls().to_list()
        self.assertTrue(vals, f"no non-null {column} for profile {profile}")
        return sum(vals) / len(vals)

    def test_pv_buildings_show_strong_negative_solar_correlation(self):
        pv_corr = self._mean_for_profile("correlation_solar_radiation_consumption", "pv")
        baseline_corr = self._mean_for_profile("correlation_solar_radiation_consumption", "baseline")
        self.assertLess(pv_corr, -0.6)
        self.assertLess(pv_corr, baseline_corr - 0.3)

    def test_heatpump_buildings_show_strong_negative_temperature_correlation(self):
        hp_corr = self._mean_for_profile("correlation_outside_temperature_consumption", "heatpump")
        baseline_corr = self._mean_for_profile("correlation_outside_temperature_consumption", "baseline")
        self.assertLess(hp_corr, -0.5)
        self.assertLess(hp_corr, baseline_corr - 0.3)

    def test_battery_buildings_have_more_near_zero_intervals_than_baseline(self):
        battery_ratio = self._mean_for_profile("near_zero_interval_ratio", "battery")
        baseline_ratio = self._mean_for_profile("near_zero_interval_ratio", "baseline")
        self.assertGreater(battery_ratio, baseline_ratio + 0.05)

    def test_ev_buildings_have_candidate_sessions_baseline_mostly_does_not(self):
        ev_gp_nrs = [gp for gp, b in self.truth.items() if b["profile"] == "pv_ev"]
        ev_sessions = (
            self.df.filter(pl.col("gp_nr").is_in(ev_gp_nrs)).get_column("sessions_per_week").drop_nulls()
        )
        self.assertGreater(ev_sessions.mean(), 1.0)

    def test_labels_are_null_for_unlabeled_buildings_not_zero(self):
        unlabeled_gp_nrs = [gp for gp, b in self.truth.items() if not b["labeled"]]
        sub = self.df.filter(pl.col("gp_nr").is_in(unlabeled_gp_nrs))
        for col in ("label_pv", "label_ev", "label_heatpump", "label_battery"):
            self.assertTrue(sub.get_column(col).is_null().all(), col)

    def test_limit_buildings_restricts_output(self):
        with tempfile.TemporaryDirectory() as tmp2:
            root2 = Path(tmp2)
            paths2 = PathsConfig(
                raw_consumption_dir=self.input_dir,
                mp_mapping_file=self.input_dir / "mpid_zähler_mapping.csv",
                zaehler_gp_file=self.input_dir / "Zähler-GP.csv",
                labels_file=self.input_dir / "HackDays2026 - GIGI.csv",
                weather_dir=self.input_dir / "weather",
                output_dir=root2 / "output",
                intermediate_dir=root2 / "output" / "intermediate",
            )
            cfg2 = PipelineConfig(paths=paths2)
            run_pipeline(cfg2, limit_buildings=5)
            df2 = pl.read_parquet(paths2.feature_dataset_path)
            self.assertEqual(df2.height, 5)


class CliEntrypointTests(unittest.TestCase):
    """Exercises scripts/build_feature_dataset.py's main() directly.

    The tests above call run_pipeline() straight from feature_pipeline and
    never touch argparse/main() wiring — that's exactly the code path where a
    bug (an undefined `defaults` reference) shipped and slipped past them.
    """

    def test_main_runs_end_to_end_with_cli_args(self):
        from scripts.build_feature_dataset import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            generate(input_dir, n_buildings=6, days=10, start=dt.date(2024, 7, 1), seed=3, quiet=True)
            output_dir = root / "output"

            exit_code = main(
                [
                    "--raw-consumption-dir",
                    str(input_dir),
                    "--mp-mapping-file",
                    str(input_dir / "mpid_zähler_mapping.csv"),
                    "--zaehler-gp-file",
                    str(input_dir / "Zähler-GP.csv"),
                    "--labels-file",
                    str(input_dir / "HackDays2026 - GIGI.csv"),
                    "--weather-dir",
                    str(input_dir / "weather"),
                    "--output-dir",
                    str(output_dir),
                    "--limit-buildings",
                    "6",
                ]
            )

            self.assertEqual(exit_code, 0)
            df = pl.read_parquet(output_dir / "feature_dataset.parquet")
            self.assertEqual(df.height, 6)
            dates = pl.read_parquet(output_dir / "gigi_dates.parquet")
            self.assertEqual(
                dates.schema,
                pl.Schema(
                    {
                        "gp_nr": pl.Int64,
                        "commissioned_pv": pl.Date,
                        "commissioned_ev": pl.Date,
                        "commissioned_heatpump": pl.Date,
                        "commissioned_battery": pl.Date,
                    }
                ),
            )
            self.assertEqual(set(dates["gp_nr"]), set(df["gp_nr"]))
            gigi_name = "HackDays2026 - GIGI.csv"
            self.assertEqual((output_dir / gigi_name).read_bytes(), (input_dir / gigi_name).read_bytes())
            manifest = json.loads((output_dir / "_manifest.json").read_text())
            self.assertEqual(manifest["gigi_dates"], str(output_dir / "gigi_dates.parquet"))
            self.assertEqual(manifest["gigi_labels"], str(output_dir / gigi_name))
            audit = json.loads((output_dir / "audit_report.json").read_text())
            self.assertEqual(audit["feature_table_shape"], list(df.shape))
            parts = sorted((output_dir / "intermediate/by_file").glob("*.parquet"))
            self.assertEqual(len(parts), 1)
            series = pl.read_parquet(parts[0])
            for name in ("import_kw", "export_kw", "net_kw", "power_kw"):
                self.assertEqual(series.schema[name], pl.Float32)
            self.assertEqual(audit["rows_per_part"], {str(parts[0]): series.height})
            self.assertEqual(manifest["rows_per_part"], audit["rows_per_part"])
            noon = series.filter(
                (pl.col("gp_nr") == 100001)
                & (pl.col("ts").dt.hour() == 12)
                & (pl.col("net_kw") < 0)
                & (pl.col("export_kw") > 0)
            )
            self.assertFalse(noon.is_empty())
            self.assertTrue(series["power_kw"].equals(series["net_kw"].rename("power_kw")))

            from osnova.config import LabelConfig, OsnovaSettings
            from osnova.export.build_json import find_gigi_file, load_gigi, load_labels
            from osnova.io.lastgang import BUILDING_SERIES, load_building_series
            from osnova.io.store import LABELS, Store
            from osnova.labels.build import build_labels
            from osnova.models.train import feature_columns

            settings_store = root / "downstream"
            expected_output = settings_store / "osnova/feature_output"
            expected_output.parent.mkdir(parents=True)
            expected_output.symlink_to(output_dir, target_is_directory=True)
            store = Store(OsnovaSettings(store_dir=settings_store, registry_dir=output_dir))
            self.assertEqual(find_gigi_file(output_dir), output_dir / gigi_name)
            metadata = load_gigi(output_dir)
            self.assertTrue(metadata)
            self.assertTrue(all(value["ort"] == "Synthstadt" for value in metadata.values()))
            self.assertEqual(load_labels(store)["num_mp_ids"].dtype, pl.Int32)
            labels = build_labels(df, dates, LabelConfig())
            self.assertEqual(labels.schema, LABELS)
            self.assertTrue(set(labels["gp_nr"]) <= set(df["gp_nr"]))
            self.assertTrue(all(df.schema[column].is_float() for column in feature_columns(df)))
            chart = load_building_series(store, 100001)
            self.assertEqual(chart.schema, BUILDING_SERIES)
            self.assertFalse(chart.filter((pl.col("net_kw") < 0) & (pl.col("export_kw") > 0)).is_empty())

            from unittest.mock import patch

            with patch(
                "scripts.build_feature_dataset.shutil.copyfileobj", side_effect=OSError("storage failure")
            ):
                with self.assertRaisesRegex(OSError, "storage failure"):
                    main(
                        [
                            "--raw-consumption-dir",
                            str(input_dir),
                            "--mp-mapping-file",
                            str(input_dir / "mpid_zähler_mapping.csv"),
                            "--zaehler-gp-file",
                            str(input_dir / "Zähler-GP.csv"),
                            "--labels-file",
                            str(input_dir / gigi_name),
                            "--weather-dir",
                            str(input_dir / "weather"),
                            "--output-dir",
                            str(output_dir),
                            "--limit-buildings",
                            "6",
                        ]
                    )
            self.assertFalse((output_dir / "_manifest.json").exists())
            self.assertGreater((input_dir / gigi_name).stat().st_size, 0)

    def test_cli_env_default_and_cohort_flags(self):
        import os
        from unittest.mock import patch

        from scripts.build_feature_dataset import build_arg_parser, main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "synth"
            generate(source, n_buildings=12, days=2, seed=7, quiet=True)
            with patch.dict(os.environ, {"OSNOVA_STORE_DIR": str(root / "store")}):
                self.assertEqual(
                    build_arg_parser().parse_args([]).output_dir, root / "store/osnova/feature_output"
                )
                self.assertEqual(
                    build_arg_parser().parse_args(["--output-dir", str(root / "other")]).output_dir,
                    root / "other",
                )
                result = main(
                    [
                        "--raw-consumption-dir",
                        str(source),
                        "--mp-mapping-file",
                        str(source / "mpid_zähler_mapping.csv"),
                        "--zaehler-gp-file",
                        str(source / "Zähler-GP.csv"),
                        "--labels-file",
                        str(source / "HackDays2026 - GIGI.csv"),
                        "--weather-dir",
                        str(source / "weather"),
                        "--extra-random-gps",
                        "2",
                        "--seed",
                        "12",
                        "--limit-files",
                        "1",
                    ]
                )
            self.assertEqual(result, 0)
            cohort = pl.read_parquet(root / "store/osnova/feature_output/cohort.parquet")
            self.assertEqual(cohort.filter(~pl.col("is_labeled")).height, 2)


class CommissioningDatesTests(unittest.TestCase):
    def test_dates_are_asset_specific_with_row_fallback_then_earliest(self):
        from feature_pipeline.export_labels import load_gigi_dates

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "gigi.csv"
            pl.DataFrame(
                {
                    " GP-Nr ": ["123456", "123456", "123456", "123456", "456789", "", "invalid"],
                    " PV": ["x", "X", "-", "", "-", "x", "x"],
                    "Ladestation für Elektrofahrzeuge": ["", "", "x", "-", "", "", ""],
                    "WärmePumpe": ["", "", "", "x", "", "", ""],
                    "Batterie/Speicher": ["-", "", "", "", "x", "", ""],
                    "InBetrieb-Datum": ["15.06.2025", "bad", "bad", "", "bad", "01.01.2000", "01.01.2000"],
                    "Übergabe": ["01.01.2020", "01.04.2024", "bad", "", "", "", ""],
                    "Datum Unterschrift": ["01.01.2019", "01.01.2020", "03.03.2023", "", "", "", ""],
                    "geplanter Baustart": ["01.01.2010"] * 7,
                }
            ).write_csv(path, separator=";")
            result = load_gigi_dates(path).sort("gp_nr")
            self.assertEqual(
                result.schema,
                pl.Schema(
                    {
                        "gp_nr": pl.Int64,
                        "commissioned_pv": pl.Date,
                        "commissioned_ev": pl.Date,
                        "commissioned_heatpump": pl.Date,
                        "commissioned_battery": pl.Date,
                    }
                ),
            )
            self.assertEqual(result["gp_nr"].to_list(), [123456, 456789])
            self.assertEqual(result["commissioned_pv"].to_list(), [dt.date(2024, 4, 1), None])
            self.assertEqual(result["commissioned_ev"].to_list(), [dt.date(2023, 3, 3), None])
            self.assertTrue(result["commissioned_heatpump"].is_null().all())
            self.assertTrue(result["commissioned_battery"].is_null().all())

    def test_missing_date_and_asset_columns_are_nullable(self):
        from feature_pipeline.export_labels import load_gigi_dates

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "gigi.csv"
            path.write_text("GP-Nr;PV;Datum Unterschrift\n123456;x;01.01.2022\n")
            result = load_gigi_dates(path)
            self.assertEqual(result["commissioned_pv"][0], dt.date(2022, 1, 1))
            self.assertTrue(result["commissioned_ev"].is_null().all())


class CohortTests(unittest.TestCase):
    def test_ingest_rejects_old_parts_outside_current_selection(self):
        from feature_pipeline.config import ThresholdsConfig
        from feature_pipeline.ingest import run_ingest

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "LG_AIM2Hackerdays_kWh_synth.csv"
            source.write_text("MP ID;OBIS-Code;Datum;PLZ;00:15;\npv;1-1:1.29.0*255;01.07.2024;5000;0.25;\n")
            paths = PathsConfig(raw_consumption_dir=root, intermediate_dir=root / "output/intermediate")
            paths.by_file_dir.mkdir(parents=True)
            stale = paths.by_file_dir / "old_selection.parquet"
            pl.DataFrame({"gp_nr": [999999]}).write_parquet(stale)
            original = stale.read_bytes()
            mapping = pl.DataFrame({"mp_id": ["pv"], "gp_nr": [100001]})
            with self.assertRaisesRegex(ValueError, "outside the current"):
                run_ingest(paths, ThresholdsConfig(), mapping, resume=False)
            self.assertEqual(stale.read_bytes(), original)

    def test_pv_obis_energy_balance_and_unknown_codes_survive_resume(self):
        import csv

        from feature_pipeline.config import ThresholdsConfig
        from feature_pipeline.ingest import run_ingest, scan_building_consumption

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "LG_AIM2Hackerdays_kWh_synth.csv"
            slots = [f"{minute // 60:02}:{minute % 60:02}" for minute in range(15, 1440, 15)] + ["00:00"]
            imported, exported = [0.25] * 96, [0.0] * 96
            exported[48] = 0.75
            with path.open("w", newline="") as target:
                writer = csv.writer(target, delimiter=";")
                writer.writerow(["MP ID", "OBIS-Code", "Datum", "PLZ", *slots, ""])
                for code, values in (
                    ("1-1:1.29.0*255", imported),
                    ("1-1:2.29.0*255", exported),
                    ("OTHER", [999] * 96),
                ):
                    writer.writerow(["pv", code, "01.06.2024", "5000", *values, ""])
            mapping = pl.DataFrame({"mp_id": ["pv"], "gp_nr": [1]})
            cohort = pl.DataFrame({"gp_nr": [1], "is_labeled": [True], "plz": ["5000"]})
            paths = PathsConfig(raw_consumption_dir=root, intermediate_dir=root / "output/intermediate")
            audit = run_ingest(paths, ThresholdsConfig(), mapping, cohort=cohort)
            data = pl.read_parquet(audit.parts[0]).sort("ts")
            self.assertEqual(data.height, 96)
            self.assertEqual(data["import_kw"][0], 1.0)
            self.assertEqual(data["net_kw"][48], -2.0)
            self.assertTrue(data["power_kw"].equals(data["net_kw"].rename("power_kw")))
            self.assertAlmostEqual(data["import_kw"].sum() / 4, sum(imported))
            self.assertAlmostEqual(data["export_kw"].sum() / 4, sum(exported))
            self.assertEqual(audit.ignored_obis_rows, {"OTHER": 1})
            cached = run_ingest(paths, ThresholdsConfig(), mapping, cohort=cohort)
            self.assertEqual(cached.ignored_obis_rows, audit.ignored_obis_rows)
            combined = scan_building_consumption(paths, cached.parts).sort("ts").collect()
            for name in ("import_kw", "export_kw", "net_kw", "power_kw"):
                self.assertEqual(combined[name].to_list(), data[name].to_list())

    def test_missing_export_row_is_zero_but_export_cell_stays_null(self):
        from feature_pipeline.config import ThresholdsConfig
        from feature_pipeline.ingest import ingest_one_file

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.csv"
            path.write_text(
                "MP ID;OBIS-Code;Datum;PLZ;00:15;\n"
                "no-export;1-1:1.29.0*255;01.01.2024;5000;1;\n"
                "missing-cell;1-1:1.29.0*255;01.01.2024;5000;1;\n"
                "missing-cell;1-1:2.29.0*255;01.01.2024;5000;;\n"
            )
            mapping = pl.DataFrame({"mp_id": ["no-export", "missing-cell"], "gp_nr": [1, 2]})
            lazy, _ = ingest_one_file(path, mapping, ThresholdsConfig())
            data = lazy.sort("gp_nr").collect()
            self.assertEqual(data["export_kw"].to_list(), [0.0, None])
            self.assertEqual(data["net_kw"].to_list(), [4.0, None])
            self.assertEqual(data["import_kw"].to_list(), [4.0, 4.0])

    def test_weather_uses_hour_end_labels_without_filling_gaps(self):
        import gzip

        from feature_pipeline.config import ThresholdsConfig
        from feature_pipeline.weather import load_weather

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "weather_part_1/hourly/5000"
            folder.mkdir(parents=True)
            for month, content in (
                ("01", "2024-01-31T23:00:00Z,5,10\n"),
                ("02", "2024-02-01T00:00:00Z,6,20\n2024-02-01T02:00:00Z,8,40\n"),
                ("10", "2024-10-27T00:00:00Z,1,0\n2024-10-27T01:00:00Z,2,0\n"),
            ):
                with gzip.open(folder / f"2024-{month}.csv.gz", "wt") as target:
                    target.write("timestamp_utc,temperature_2m,shortwave_radiation\n" + content)
            weather = load_weather(PathsConfig(weather_dir=root), ThresholdsConfig()).hourly
            self.assertEqual(weather.height, weather.unique(["plz", "ts"]).height)
            midnight = weather.filter(pl.col("ts") == dt.datetime(2024, 2, 1))
            self.assertEqual(midnight["temperature_2m"].item(), 5)
            self.assertEqual(midnight["shortwave_radiation"].item(), 20)
            gap = weather.filter(pl.col("ts") == dt.datetime(2024, 2, 1, 1))
            self.assertIsNone(gap["shortwave_radiation"].item())

    def test_valid_days_count_only_days_with_at_least_90_known_intervals(self):
        from feature_pipeline.features import day_level_export_ratio

        rows = []
        for offset, valid in enumerate((96, 90, 89, 0)):
            for interval in range(96):
                rows.append(
                    {
                        "gp_nr": 1,
                        "_date": dt.date(2024, 1, 1) + dt.timedelta(days=offset),
                        "power_kw": 0.0 if interval < valid else None,
                    }
                )
        rows.append({"gp_nr": 2, "_date": dt.date(2024, 1, 1), "power_kw": None})
        result = day_level_export_ratio(pl.DataFrame(rows).lazy(), PipelineConfig()).sort("gp_nr").collect()
        self.assertEqual(result["n_valid_days"].to_list(), [2, 0])
        self.assertIsNone(result["days_with_export_ratio"][1])

    def test_loader_does_not_materialize_nonweather_csvs(self):
        from unittest.mock import patch

        import feature_pipeline.weather as module
        from feature_pipeline.config import ThresholdsConfig

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            generate(root, n_buildings=4, days=1, quiet=True)
            original = module.read_csv_flexible
            loaded = []

            def read(path):
                loaded.append(path)
                return original(path)

            with patch.object(module, "read_csv_flexible", side_effect=read):
                result = module.load_weather(PathsConfig(weather_dir=root), ThresholdsConfig())
            self.assertEqual(result.hourly.height, 5 * 24)
            self.assertTrue(all(path.parent.name == "weather" for path in loaded))

    def test_pipeline_writes_cohort_and_invalidates_changed_cohort_cache(self):
        from feature_pipeline.config import CohortConfig
        from feature_pipeline.labels import load_labels

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input"
            generate(source, n_buildings=16, days=3, start=dt.date(2024, 1, 1), seed=7, quiet=True)
            paths = PathsConfig(
                raw_consumption_dir=source,
                mp_mapping_file=source / "mpid_zähler_mapping.csv",
                zaehler_gp_file=source / "Zähler-GP.csv",
                labels_file=source / "HackDays2026 - GIGI.csv",
                weather_dir=source / "weather",
                output_dir=root / "output",
                intermediate_dir=root / "output/intermediate",
            )
            config = PipelineConfig(paths=paths, cohort=CohortConfig(extra_random_gps=2))
            labels = load_labels(paths)
            labeled = set(labels["gp_nr"].to_list())
            run_pipeline(config)
            cohort = pl.read_parquet(paths.output_dir / "cohort.parquet")
            self.assertEqual(cohort.height, len(labeled) + 2)
            self.assertEqual(set(cohort.filter("is_labeled")["gp_nr"]), labeled)
            self.assertEqual(cohort["gp_nr"].dtype, pl.Int64)
            self.assertTrue(cohort["plz"].is_not_null().all())
            timeline = pl.read_parquet(list(paths.by_file_dir.glob("*.parquet")))
            self.assertEqual(set(timeline["gp_nr"]), set(cohort["gp_nr"]))
            output = pl.read_parquet(paths.feature_dataset_path)
            self.assertEqual(set(output["gp_nr"]), set(cohort["gp_nr"]))
            manifest = json.loads((paths.output_dir / "_manifest.json").read_text())
            self.assertEqual(manifest["rows"], cohort.height)
            self.assertEqual(run_pipeline(config).number_of_files_skipped_cached, 1)
            smaller = replace(config, cohort=CohortConfig(labeled_only=True))
            with self.assertRaisesRegex(ValueError, "configuration"):
                run_pipeline(smaller)
            run_pipeline(smaller, resume=False)
            smaller_output = pl.read_parquet(paths.feature_dataset_path)
            self.assertEqual(set(smaller_output["gp_nr"]), labeled)

    def test_cohort_keeps_joined_known_labels_and_seeded_extras(self):
        from feature_pipeline.config import CohortConfig
        from feature_pipeline.ingest import select_cohort

        mapping = pl.DataFrame(
            {
                "gp_nr": [1, 1, 2, 3, 4, 5, 6],
                "mp_id": ["m1", "m2", "m3", "m4", "m5", "m6", None],
            }
        )
        labels = pl.DataFrame(
            {
                "gp_nr": [1, 2, 6, 99],
                "plz": ["5000", "5105", "5105", "5000"],
                "label_pv": [0, None, 1, 1],
                "label_ev": [None] * 4,
                "label_heatpump": [None] * 4,
                "label_battery": [None] * 4,
            }
        )
        config = CohortConfig(extra_random_gps=2, seed=42)
        cohort = select_cohort(mapping, labels, config)
        self.assertEqual(
            cohort.schema, pl.Schema({"gp_nr": pl.Int64, "is_labeled": pl.Boolean, "plz": pl.String})
        )
        self.assertEqual(cohort.height, 3)
        self.assertEqual(cohort.filter("is_labeled")["gp_nr"].to_list(), [1])
        self.assertEqual(cohort.filter("is_labeled")["plz"].to_list(), ["5000"])
        self.assertTrue(cohort.equals(select_cohort(mapping.reverse(), labels.reverse(), config)))
        self.assertEqual(select_cohort(mapping, labels, CohortConfig(labeled_only=True)).height, 1)
        self.assertEqual(select_cohort(mapping, labels, CohortConfig(extra_random_gps=0)).height, 1)
        self.assertEqual(select_cohort(mapping, labels, CohortConfig()).height, 6)
        with self.assertRaises(ValueError):
            CohortConfig(extra_random_gps=-1)

    def test_ingest_filters_cohort_and_produces_net_kw_with_nulls(self):
        from feature_pipeline.config import ThresholdsConfig
        from feature_pipeline.ingest import ingest_one_file

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "LG_AIM2Hackerdays_kWh_synth.csv"
            path.write_text(
                "MP ID;OBIS-Code;Datum;PLZ;00:15;00:30;00:00;\n"
                "m1;1-1:1.29.0*255;01.01.2024;5000;1.0;;0.25;\n"
                "m1;1-1:2.29.0*255;01.01.2024;5000;0.25;0.0;0.5;\n"
                "m2;1-1:1.29.0*255;01.01.2024;5000;0.5;0.5;;\n"
                "m2;1-1:2.29.0*255;01.01.2024;5000;0;0;;\n"
                "excluded;1-1:1.29.0*255;01.01.2024;5105;999;999;999;\n"
            )
            mapping = pl.DataFrame({"mp_id": ["m1", "m2", "excluded"], "gp_nr": [1, 1, 2]})
            cohort = pl.DataFrame({"gp_nr": [1], "is_labeled": [True], "plz": ["5000"]})
            lazy, seen = ingest_one_file(path, mapping, ThresholdsConfig(), cohort=cohort)
            result = lazy.sort("ts").collect()
            self.assertEqual(result["gp_nr"].unique().to_list(), [1])
            self.assertEqual(result["power_kw"].to_list(), [5.0, None, None])
            self.assertEqual(result["num_mp_with_data"].to_list(), [2, 1, 1])
            self.assertEqual(
                result["ts"].to_list(),
                [dt.datetime(2024, 1, 1), dt.datetime(2024, 1, 1, 0, 15), dt.datetime(2024, 1, 1, 23, 45)],
            )
            self.assertEqual(seen, {"m1", "m2", "excluded"})


if __name__ == "__main__":
    unittest.main()
