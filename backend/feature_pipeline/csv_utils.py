"""Small, dependency-free helpers for reading the messy real-world CSVs.

Real header names use German umlauts and inconsistent delimiters/encodings.
Rather than hard-coding one exact spelling, columns are matched by a
normalised form (lower-cased, accents/umlauts folded, non-alphanumerics
stripped) so a harmless header variation does not break the pipeline.
"""

from __future__ import annotations

import csv
import gzip
import io
from pathlib import Path

import polars as pl


def _is_gzip(path: Path) -> bool:
    return path.name.lower().endswith(".gz")


def _read_bytes(path: Path) -> bytes:
    """Read a file's content, transparently gunzipping ``*.gz`` files."""
    if _is_gzip(path):
        with gzip.open(path, "rb") as fh:
            return fh.read()
    return path.read_bytes()


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
    if _is_gzip(path):
        with gzip.open(path, "rb") as fh:
            first_line = fh.readline()
    else:
        with open(path, "rb") as fh:
            first_line = fh.readline()
    text = first_line.decode("utf-8-sig", errors="replace")
    counts = {c: text.count(c) for c in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_csv_header(path: Path) -> list[str]:
    opener = gzip.open if _is_gzip(path) else open
    with opener(path, "rt", encoding="utf-8-sig", errors="replace", newline="") as source:
        return next(csv.reader(source, delimiter=sniff_delimiter(path)), [])


def find_column(columns: list[str], *candidates: str) -> str | None:
    """Find the real column name matching one of ``candidates`` (normalised)."""
    lookup = {normalise(c): c for c in columns}
    for cand in candidates:
        hit = lookup.get(normalise(cand))
        if hit is not None:
            return hit
    return None


def read_csv_flexible(path: Path, **kwargs) -> pl.DataFrame:
    """Read a CSV with an auto-detected delimiter and a BOM-tolerant encoding.

    Transparently gunzips ``*.gz`` files (polars' own gzip support varies by
    version, so this decompresses in Python and hands it a byte buffer).
    """
    delimiter = sniff_delimiter(path)
    source = io.BytesIO(_read_bytes(path)) if _is_gzip(path) else path
    kwargs.setdefault("infer_schema_length", 10_000)
    return pl.read_csv(
        source,
        separator=delimiter,
        encoding="utf8-lossy",
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
