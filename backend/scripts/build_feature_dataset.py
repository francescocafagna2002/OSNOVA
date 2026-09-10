#!/usr/bin/env python3
"""CLI entrypoint for the building-level feature extraction pipeline.

Run from ``backend/`` (this script imports ``feature_pipeline`` as a
top-level package, same convention as ``scripts/preview_data.py``):

    python3 scripts/build_feature_dataset.py \
        --raw-consumption-dir /path/to/aew-data/test-blob/input_data \
        --mp-mapping-file /path/to/mpid_zähler_mapping.csv \
        --zaehler-gp-file /path/to/Zähler-GP.csv \
        --labels-file "/path/to/HackDays2026 - GIGI.csv" \
        --weather-dir /path/to/weather \
        --output-dir data/feature_output

Add ``--limit-buildings 100`` for a fast development run, and
``--limit-files N`` to additionally cap how many consumption CSVs are read
(dev-only speed lever; a full run needs every file since a sampled building's
meter can appear in any of them).

Re-running is incremental: already-ingested consumption files are skipped
(tracked in ``<output-dir>/intermediate/ingest_manifest.json``) unless
``--no-resume`` is passed.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from feature_pipeline.config import PathsConfig, PipelineConfig, ThresholdsConfig
from feature_pipeline.pipeline import run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    defaults = PathsConfig()
    parser.add_argument("--raw-consumption-dir", type=Path, default=defaults.raw_consumption_dir)
    parser.add_argument("--raw-consumption-glob", default=defaults.raw_consumption_glob)
    parser.add_argument("--mp-mapping-file", type=Path, default=defaults.mp_mapping_file)
    parser.add_argument("--zaehler-gp-file", type=Path, default=defaults.zaehler_gp_file)
    parser.add_argument("--labels-file", type=Path, default=defaults.labels_file)
    parser.add_argument(
        "--weather-dir", type=Path, nargs="+", default=[defaults.weather_dir],
        help="One or more weather root directories (e.g. both weather_part_1 "
             "and weather_part_2 if they don't share a parent). PLZ is read "
             "from each file's parent directory name (real layout: "
             "<root>/hourly/<PLZ>/YYYY-MM.csv.gz).",
    )
    parser.add_argument(
        "--weather-glob", action="append", default=None,
        help=f"Glob pattern for weather files under each --weather-dir root; "
             f"repeatable. Default: {list(defaults.weather_globs)}.",
    )
    parser.add_argument("--output-dir", type=Path, default=defaults.output_dir)
    parser.add_argument("--intermediate-dir", type=Path, default=None)
    parser.add_argument(
        "--limit-buildings", type=int, default=None,
        help="Process only the first N buildings (by GP-Nr) — fast development run.",
    )
    parser.add_argument(
        "--limit-files", type=int, default=None,
        help="Read only the first N consumption CSVs — dev-only, not exhaustive.",
    )
    parser.add_argument("--no-resume", action="store_true", help="Ignore the ingest checkpoint and reprocess every file.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    defaults = PathsConfig()
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    intermediate_dir = args.intermediate_dir or (args.output_dir / "intermediate")
    paths = PathsConfig(
        raw_consumption_dir=args.raw_consumption_dir,
        raw_consumption_glob=args.raw_consumption_glob,
        mp_mapping_file=args.mp_mapping_file,
        zaehler_gp_file=args.zaehler_gp_file,
        labels_file=args.labels_file,
        weather_dir=args.weather_dir[0],
        weather_dirs=tuple(args.weather_dir),
        weather_globs=tuple(args.weather_glob) if args.weather_glob else defaults.weather_globs,
        output_dir=args.output_dir,
        intermediate_dir=intermediate_dir,
    )
    cfg = PipelineConfig(paths=paths, thresholds=ThresholdsConfig())

    for label, path in (
        ("raw consumption dir", paths.raw_consumption_dir),
        ("MP mapping file", paths.mp_mapping_file),
        ("Zähler-GP file", paths.zaehler_gp_file),
        ("labels file", paths.labels_file),
    ):
        if not path.exists():
            print(f"Error: {label} not found: {path}", file=sys.stderr)
            return 1

    run_pipeline(
        cfg,
        limit_buildings=args.limit_buildings,
        limit_files=args.limit_files,
        resume=not args.no_resume,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
