#!/usr/bin/env python3
"""Print the header and first ten records of each CSV in the data mount."""

import argparse
import csv
import gzip
import sys
from itertools import islice
from pathlib import Path


def find_data_dir():
    cwd = Path.cwd()
    for base in (cwd, *cwd.parents):
        for name in ("aew-data", "aew_data", "data/aew-data", "data/aew_data"):
            candidate = base / name
            if candidate.is_dir():
                return candidate
    raise FileNotFoundError("No aew-data or aew_data mount found. Pass its full path as an argument.")


def is_csv(path):
    return path.name.lower().endswith((".csv", ".csv.gz"))


def preview(path):
    print(f"\n=== {path} ===", flush=True)
    opener = gzip.open if path.name.lower().endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as source:
        sample = source.read(8192)
        source.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            try:
                dialect = csv.Sniffer().sniff(sample.partition("\n")[0], delimiters=",;\t|")
            except csv.Error:
                dialect = csv.excel
        reader = csv.reader(source, dialect)
        writer = csv.writer(sys.stdout, dialect, lineterminator="\n")
        writer.writerows(islice(reader, 11))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="CSV file or directory; defaults to the nearby aew-data/aew_data mount",
    )
    args = parser.parse_args()
    try:
        root = args.path.expanduser() if args.path is not None else find_data_dir()
        if not root.exists():
            raise FileNotFoundError(f"Path does not exist: {root}")
        candidates = [root] if root.is_file() else root.rglob("*")
        files = sorted(path for path in candidates if is_csv(path) and path.is_file())
        if not files:
            raise FileNotFoundError(f"No .csv or .csv.gz files found in: {root}")
    except OSError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    failed = False
    for path in files:
        try:
            preview(path)
        except (OSError, EOFError, csv.Error) as error:
            print(f"Error reading {path}: {error}", file=sys.stderr)
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
