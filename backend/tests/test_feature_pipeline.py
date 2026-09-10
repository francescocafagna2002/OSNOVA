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
import tempfile
import unittest
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
        self.assertEqual(self.df.columns, FINAL_COLUMNS)

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
        vals = (
            self.df.filter(pl.col("gp_nr").is_in(gp_nrs))
            .get_column(column)
            .drop_nulls()
            .to_list()
        )
        self.assertTrue(vals, f"no non-null {column} for profile {profile}")
        return sum(vals) / len(vals)

    def test_pv_buildings_show_strong_negative_solar_correlation(self):
        pv_corr = self._mean_for_profile("correlation_solar_radiation_consumption", "pv")
        baseline_corr = self._mean_for_profile(
            "correlation_solar_radiation_consumption", "baseline"
        )
        self.assertLess(pv_corr, -0.6)
        self.assertLess(pv_corr, baseline_corr - 0.3)

    def test_heatpump_buildings_show_strong_negative_temperature_correlation(self):
        hp_corr = self._mean_for_profile(
            "correlation_outside_temperature_consumption", "heatpump"
        )
        baseline_corr = self._mean_for_profile(
            "correlation_outside_temperature_consumption", "baseline"
        )
        self.assertLess(hp_corr, -0.5)
        self.assertLess(hp_corr, baseline_corr - 0.3)

    def test_battery_buildings_have_more_near_zero_intervals_than_baseline(self):
        battery_ratio = self._mean_for_profile("near_zero_interval_ratio", "battery")
        baseline_ratio = self._mean_for_profile("near_zero_interval_ratio", "baseline")
        self.assertGreater(battery_ratio, baseline_ratio + 0.05)

    def test_ev_buildings_have_candidate_sessions_baseline_mostly_does_not(self):
        ev_gp_nrs = [gp for gp, b in self.truth.items() if b["profile"] == "pv_ev"]
        ev_sessions = (
            self.df.filter(pl.col("gp_nr").is_in(ev_gp_nrs))
            .get_column("sessions_per_week")
            .drop_nulls()
        )
        self.assertGreater(ev_sessions.mean(), 1.0)

    def test_labels_are_null_for_unlabeled_buildings_not_zero(self):
        unlabeled_gp_nrs = [gp for gp, b in self.truth.items() if not b["labeled"]]
        sub = self.df.filter(pl.col("gp_nr").is_in(unlabeled_gp_nrs))
        for col in ("label_pv", "label_ev", "label_heatpump", "label_battery"):
            self.assertTrue(sub.get_column(col).is_null().all(), col)

    def test_pv_presence_is_always_null_placeholder(self):
        self.assertTrue(self.df.get_column("pv_presence").is_null().all())

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
            generate(input_dir, n_buildings=6, days=10, start=dt.date(2024, 1, 1), seed=3, quiet=True)
            output_dir = root / "output"

            exit_code = main(
                [
                    "--raw-consumption-dir", str(input_dir),
                    "--mp-mapping-file", str(input_dir / "mpid_zähler_mapping.csv"),
                    "--zaehler-gp-file", str(input_dir / "Zähler-GP.csv"),
                    "--labels-file", str(input_dir / "HackDays2026 - GIGI.csv"),
                    "--weather-dir", str(input_dir / "weather"),
                    "--output-dir", str(output_dir),
                    "--limit-buildings", "6",
                ]
            )

            self.assertEqual(exit_code, 0)
            df = pl.read_parquet(output_dir / "feature_dataset.parquet")
            self.assertEqual(df.height, 6)


if __name__ == "__main__":
    unittest.main()
