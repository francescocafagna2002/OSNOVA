"""Small, dependency-free helpers for reading the messy real-world CSVs.

Real header names use German umlauts and inconsistent delimiters/encodings.
Rather than hard-coding one exact spelling, columns are matched by a
normalised form (lower-cased, accents/umlauts folded, non-alphanumerics
stripped) so a harmless header variation does not break the pipeline.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

_UMLAUT_FOLD = str.maketrans(
    {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "ae",
        "Ö": "oe",
        "Ü": "ue",
        "ß": "ss",
    }
)


def normalise(name: str) -> str:
    folded = name.strip().translate(_UMLAUT_FOLD).lower()
    return "".join(ch for ch in folded if ch.isalnum())


def sniff_delimiter(path: Path, candidates: str = ";,\t|") -> str:
    """Pick the delimiter that appears most consistently in the first line."""
    with open(path, "rb") as fh:
        first_line = fh.readline()
    text = first_line.decode("utf-8-sig", errors="replace")
    counts = {c: text.count(c) for c in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def find_column(columns: list[str], *candidates: str) -> str | None:
    """Find the real column name matching one of ``candidates`` (normalised)."""
    lookup = {normalise(c): c for c in columns}
    for cand in candidates:
        hit = lookup.get(normalise(cand))
        if hit is not None:
            return hit
    return None


def read_csv_flexible(path: Path, **kwargs) -> pl.DataFrame:
    """Read a CSV with an auto-detected delimiter and a BOM-tolerant encoding."""
    delimiter = sniff_delimiter(path)
    return pl.read_csv(
        path,
        separator=delimiter,
        encoding="utf8-lossy",
        infer_schema_length=10_000,
        try_parse_dates=False,
        **kwargs,
    )


def scan_csv_flexible(path: Path, **kwargs) -> pl.LazyFrame:
    delimiter = sniff_delimiter(path)
    return pl.scan_csv(
        path,
        separator=delimiter,
        encoding="utf8-lossy",
        infer_schema_length=10_000,
        try_parse_dates=False,
        **kwargs,
    )
