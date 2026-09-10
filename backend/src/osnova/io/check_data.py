# src/osnova/io/check_data.py
"""`osnova check-data`: measure the facts the pipeline depends on (OBIS, units, DST, joins, weather).

Runs on the real mount on Renku and on synth locally. Everything here is a *measurement*, never a
transformation: the report is written to `data_check.json`, printed as markdown, and committed to
`docs/superpowers/specs/data-check-<date>.md` so laptop-only sessions work from facts.
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from osnova.config import Config

TABLE1_HEADER_PREFIX = "MP ID;OBIS-Code"
SLOT_RE = re.compile(r"^\d{1,2}:\d{2}$")
YEAR_RE = re.compile(r"(20\d{2})")
# a Table 1 file that probably contains March: 2023-03, 2023_03, _03_, -03., "März", "Maerz"
MARCH_FILE_RE = re.compile(r"(?i)(20\d{2}[-_.]?03(?!\d)|[-_]03[-_.]|m(ä|ae)rz)")
DST_SLOTS = ("02:15", "02:30", "02:45", "03:00")
DAILY_SUM_SAMPLE_ROWS = 2000
KW_THRESHOLD_DAILY_SUM = 40.0  # design §2.2: kWh/15 min days sum to ~5-40, kW rows to ~20-160


# --------------------------------------------------------------------------- helpers


def _first_line(path: Path) -> str:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:  # type: ignore[operator]
        raw = fh.readline()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _scan_csv(path: Path, separator: str) -> pl.LazyFrame:
    kwargs: dict[str, Any] = dict(
        separator=separator, truncate_ragged_lines=True, infer_schema_length=0, encoding="utf8-lossy"
    )
    if path.suffix == ".gz":
        return pl.read_csv(path, **kwargs).lazy()
    return pl.scan_csv(path, **kwargs)


def _normalize_slot(name: str) -> str | None:
    """'2:15' / '02:15' -> '02:15'; anything else -> None."""
    if not SLOT_RE.match(name.strip()):
        return None
    hh, mm = name.strip().split(":")
    return f"{int(hh):02d}:{mm}"


def _to_float(col: str) -> pl.Expr:
    return pl.col(col).str.strip_chars().str.replace(",", ".", literal=True).cast(pl.Float64, strict=False)


def _last_sunday_of_march(year: int) -> date:
    end = date(year, 3, 31)
    return end - timedelta(days=(end.weekday() + 1) % 7)


def _year_of(path: Path) -> str:
    m = YEAR_RE.search(str(path))
    return m.group(1) if m else "unknown"


# --------------------------------------------------------------------------- table 1


def find_table1_files(data_dir: Path) -> list[Path]:
    files = [p for p in sorted(data_dir.rglob("*.csv*")) if p.is_file()]
    return [p for p in files if _first_line(p).startswith(TABLE1_HEADER_PREFIX)]


def _check_table1(files: list[Path], cfg: Config, max_files: int) -> dict[str, Any]:
    sep = cfg.ingest.csv_separator
    per_year: dict[str, list[str]] = {}
    for p in files:
        per_year.setdefault(_year_of(p), []).append(p.name)
    sampled = files[:max_files]
    obis_counts: Counter[str] = Counter()
    daily_sums: list[pl.Series] = []
    plz_values: set[str] = set()
    sampled_info: list[dict[str, Any]] = []
    for path in sampled:
        lf = _scan_csv(path, sep)
        cols = lf.collect_schema().names()
        slot_map = {n: c for c in cols if (n := _normalize_slot(c)) is not None}
        slot_cols = list(slot_map.values())
        for code, n in lf.group_by("OBIS-Code").len().collect().iter_rows():
            obis_counts[str(code)] += int(n)
        imp = lf.filter(pl.col("OBIS-Code") == cfg.ingest.import_obis)
        if slot_cols:
            sums = (
                imp.head(DAILY_SUM_SAMPLE_ROWS)
                .select(pl.sum_horizontal([_to_float(c) for c in slot_cols]).alias("daily_sum"))
                .collect()["daily_sum"]
            )
            daily_sums.append(sums)
        datum = _datum(lf, cfg)
        if "PLZ" in cols:
            plz_values |= {str(v).strip() for v in lf.select("PLZ").unique().collect()["PLZ"].drop_nulls()}
        sampled_info.append(
            {
                "file": str(path),
                "rows": int(lf.select(pl.len()).collect().item()),
                "n_slot_columns": len(slot_cols),
                "non_slot_columns": [c for c in cols if c not in slot_cols],
                "date_min": str(datum.min()),
                "date_max": str(datum.max()),
            }
        )
    all_sums = pl.concat(daily_sums) if daily_sums else pl.Series("daily_sum", [], pl.Float64)
    median = float(all_sums.median()) if all_sums.len() else None
    return {
        "files": {"count": len(files), "per_year": per_year, "sampled": sampled_info},
        "obis_counts": dict(sorted(obis_counts.items())),
        "unit_guess": "kwh_per_15min" if median is not None and median < KW_THRESHOLD_DAILY_SUM else "kw",
        "daily_sum_median": median,
        "daily_sum_quantiles": {
            q: (float(all_sums.quantile(float(q))) if all_sums.len() else None) for q in ("0.1", "0.5", "0.9")
        },
        "daily_sum_rows": int(all_sums.len()),
        "dst_null_cells": _check_dst(files, sampled, cfg),
        "_plz_in_table1": sorted(plz_values),
    }


def _datum(lf: pl.LazyFrame, cfg: Config) -> pl.Series:
    return lf.select(
        pl.col("Datum").str.strip_chars().str.strptime(pl.Date, cfg.ingest.date_format, strict=False)
    ).collect()["Datum"]


def _check_dst(files: list[Path], sampled: list[Path], cfg: Config) -> dict[str, Any]:
    """Nulls in the 02:15..03:00 cells on the last Sunday of March.

    The sampled files rarely contain March, so files whose name looks like a March file are scanned
    too. A year whose spring-forward day is in none of the scanned files is reported as unchecked.
    """
    candidates = list(sampled) + [f for f in files if f not in sampled and MARCH_FILE_RE.search(f.name)]
    cells: dict[str, int] = dict.fromkeys(DST_SLOTS, 0)
    days_checked: list[str] = []
    files_checked: list[str] = []
    for path in candidates:
        lf = _scan_csv(path, cfg.ingest.csv_separator)
        slot_map = {n: c for c in lf.collect_schema().names() if (n := _normalize_slot(c)) is not None}
        present = [s for s in DST_SLOTS if s in slot_map]
        datum = _datum(lf, cfg).drop_nulls()
        if not present or datum.len() == 0:
            continue
        lo, hi = datum.min(), datum.max()
        for year in range(lo.year, hi.year + 1):
            day = _last_sunday_of_march(year)
            if not (lo <= day <= hi):
                continue
            day_str = day.strftime(cfg.ingest.date_format)
            nulls = (
                lf.filter(pl.col("Datum").str.strip_chars() == day_str)
                .select(
                    pl.len().alias("n_rows"),
                    *[_to_float(slot_map[s]).is_null().sum().alias(s) for s in present],
                )
                .collect()
            )
            if int(nulls["n_rows"][0]) == 0:
                continue
            days_checked.append(day_str)
            files_checked.append(path.name)
            for s in present:
                cells[s] += int(nulls[s][0])
    return {
        **cells,
        "total": sum(cells.values()),
        "days_checked": days_checked,
        "files_checked": files_checked,
    }


# --------------------------------------------------------------------------- registry


def _read_table(path: Path, separator: str) -> pl.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xlsm", ".xls"):
        return pl.read_excel(path)
    return pl.read_csv(
        path, separator=separator, truncate_ragged_lines=True, infer_schema_length=0, encoding="utf8-lossy"
    )


def _has(cols: list[str], needle: str) -> str | None:
    """First column whose name contains `needle` (case-insensitive), else None."""
    low = needle.lower()
    return next((c for c in cols if low in c.lower()), None)


def find_registry_files(data_dir: Path, separator: str) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".csv", ".xlsx", ".xlsm", ".xls"):
            continue
        if p.suffix.lower() == ".csv":
            header = _first_line(p)
            if header.startswith(TABLE1_HEADER_PREFIX):
                continue
            cols = [c.strip().strip('"') for c in header.split(separator)]
        else:
            try:
                cols = pl.read_excel(p, read_options={"n_rows": 0, "dtypes": "string"}).columns
            except Exception:  # noqa: BLE001 - unreadable workbook is reported, not fatal
                continue
        if _has(cols, "GP-Nr") and "table2" not in found:
            found["table2"] = p
        elif _has(cols, "MP ID") and _has(cols, "punktbezeichnung") and "table3" not in found:
            found["table3"] = p
        elif _has(cols, "GPartner") and "table4" not in found:
            found["table4"] = p
    return found


def _check_registry(data_dir: Path, cfg: Config) -> dict[str, Any]:
    sep = cfg.ingest.csv_separator
    paths = find_registry_files(data_dir, sep)
    out: dict[str, Any] = {"files": {k: str(v) for k, v in paths.items()}, "columns": {}}
    tables = {k: _read_table(v, sep) for k, v in paths.items()}
    for k, df in tables.items():
        out["columns"][k] = df.columns
        out[f"n_rows_{k}"] = df.height
    if set(tables) != {"table2", "table3", "table4"}:
        out["missing_tables"] = sorted({"table2", "table3", "table4"} - set(tables))
        out.update(n_gp=None, n_meters_table3=None, n_meters_joined=None, meters_per_gp_hist={})
        return out
    t2, t3, t4 = tables["table2"], tables["table3"], tables["table4"]
    gp2, zp3, zp4, gp4 = (
        _has(t2.columns, "GP-Nr"),
        _has(t3.columns, "punktbezeichnung"),
        _has(t4.columns, "punktbezeichnung"),
        _has(t4.columns, "GPartner"),
    )
    mp3 = _has(t3.columns, "MP ID")
    key = lambda c: pl.col(c).cast(pl.String).str.strip_chars()  # noqa: E731
    t2k = t2.select(gp=key(gp2)).drop_nulls().unique()
    t3k = t3.select(meter=key(mp3), zp=key(zp3)).drop_nulls()
    t4k = t4.select(zp=key(zp4), gp=key(gp4)).drop_nulls().unique()
    joined = t3k.join(t4k, on="zp", how="inner").join(t2k, on="gp", how="inner").unique(["meter", "gp"])
    per_gp = joined.group_by("gp").agg(pl.col("meter").n_unique().alias("n"))
    hist = {str(k): int(v) for k, v in sorted(per_gp["n"].value_counts().iter_rows())}
    out.update(
        n_gp=t2k.height,
        n_meters_table3=int(t3k["meter"].n_unique()),
        n_meters_joined=int(joined["meter"].n_unique()),
        n_gp_with_meter=int(joined["gp"].n_unique()),
        n_gp_without_meter=int(t2k.height - joined["gp"].n_unique()),
        meters_per_gp_hist=hist,
        asset_counts=_asset_counts(t2),
    )
    return out


def _asset_counts(t2: pl.DataFrame) -> dict[str, int]:
    """Rows in Table 2 flagged per asset column (any non-null, non-empty, non-'nein' value)."""
    counts: dict[str, int] = {}
    for col in t2.columns:
        s = t2[col]
        if s.dtype != pl.String:
            continue
        low = s.str.strip_chars().str.to_lowercase()
        if low.drop_nulls().is_in(["ja", "x", "1", "true", "yes"]).any():
            counts[col] = int(low.is_in(["ja", "x", "1", "true", "yes"]).sum())
    return counts


# --------------------------------------------------------------------------- weather


def _check_weather(weather_dir: Path, plz_in_table1: list[str]) -> dict[str, Any]:
    files = sorted(p for p in weather_dir.glob("*.csv") if p.is_file()) if weather_dir.exists() else []
    out: dict[str, Any] = {"dir": str(weather_dir), "files": [p.name for p in files], "columns": []}
    plz_with_weather: set[str] = set()
    hour_gaps = 0
    for i, p in enumerate(files):
        df = pl.read_csv(p, infer_schema_length=0, encoding="utf8-lossy")
        if i == 0:
            out["columns"] = df.columns
            out["rows_first_file"] = df.height
            tcol = next((c for c in df.columns if c.lower() in ("time", "datetime", "date")), None)
            if tcol:
                ts = df[tcol].str.strptime(pl.Datetime("ms"), "%Y-%m-%dT%H:%M", strict=False).drop_nulls()
                out["time_min"], out["time_max"] = str(ts.min()), str(ts.max())
                if ts.len() > 1:
                    hour_gaps = int((ts.sort().diff().drop_nulls() != timedelta(hours=1)).sum())
        if "plz" in df.columns:
            plz_with_weather |= {v.strip() for v in df["plz"].drop_nulls().unique()}
        else:
            m = re.search(r"(\d{4})", p.stem)
            if m:
                plz_with_weather.add(m.group(1))
    out["hour_gaps"] = hour_gaps
    out["plz_in_table1"] = sorted(plz_in_table1)
    out["plz_with_weather"] = sorted(plz_with_weather)
    out["plz_missing"] = sorted(set(plz_in_table1) - plz_with_weather)
    return out


# --------------------------------------------------------------------------- public


def run_check(data_dir: Path, weather_dir: Path, cfg: Config, max_files: int = 3) -> dict:
    """Measure Table 1 (sampled), the registry tables and the weather directory. Pure read-only."""
    files = find_table1_files(data_dir)
    t1 = _check_table1(files, cfg, max_files)
    plz_in_table1 = t1.pop("_plz_in_table1")
    return {
        "data_dir": str(data_dir),
        "config": {
            "import_obis": cfg.ingest.import_obis,
            "export_obis": cfg.ingest.export_obis,
            "unit_factor": cfg.ingest.unit_factor,
            "csv_separator": cfg.ingest.csv_separator,
            "date_format": cfg.ingest.date_format,
        },
        **t1,
        "registry": _check_registry(data_dir, cfg),
        "weather": _check_weather(weather_dir, plz_in_table1),
    }


def to_markdown(report: dict) -> str:
    lines = ["# data check", ""]
    for key, value in report.items():
        lines += [
            f"## {key}",
            "",
            "```json",
            json.dumps(value, indent=2, ensure_ascii=False, default=str),
            "```",
            "",
        ]
    return "\n".join(lines)
