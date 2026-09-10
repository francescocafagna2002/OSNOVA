# src/osnova/io/check_data.py
"""`osnova check-data`: measure the facts the pipeline depends on (OBIS, units, DST, joins, weather).

Runs on the real mount on Renku and on synth locally. Everything here is a *measurement*, never a
transformation: the report is written to `data_check.json`, printed as markdown, and committed to
`docs/superpowers/specs/data-check-<date>.md` so laptop-only sessions work from facts.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from osnova.config import Config
from osnova.io.weather import find_weather_files, first_line, plz_of_weather_file, read_raw

TABLE1_HEADER_PREFIX = "MP ID;OBIS-Code"
SLOT_RE = re.compile(r"^\d{1,2}:\d{2}$")
YEAR_RE = re.compile(r"(20\d{2})")
# a Table 1 file that probably contains March: 2023-03, 2023_03, _03_, -03., "März", "Maerz"
MARCH_FILE_RE = re.compile(r"(?i)(20\d{2}[-_.]?03(?!\d)|[-_]03[-_.]|m(ä|ae)rz)")
DST_SLOTS = ("02:15", "02:30", "02:45", "03:00")
DAILY_SUM_SAMPLE_ROWS = 2000
KW_THRESHOLD_DAILY_SUM = 40.0  # design §2.2: kWh/15 min days sum to ~5-40, kW rows to ~20-160


# --------------------------------------------------------------------------- helpers


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
    """Year folder first (`2023/März 2023/LG_…_20260827.csv` is 2023, not the export date in the name)."""
    for part in reversed(path.parts[:-1]):
        m = YEAR_RE.search(part)
        if m:
            return m.group(1)
    m = YEAR_RE.search(path.name)
    return m.group(1) if m else "unknown"


def is_march_file(path: Path, root: Path) -> bool:
    """Name or folder says March: `2023-03`, `_03_`, `März 2023`, `Maerz` … (the real mount uses folders)."""
    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    return MARCH_FILE_RE.search(rel) is not None


# --------------------------------------------------------------------------- table 1


def find_table1_files(data_dir: Path) -> list[Path]:
    files = [p for p in sorted(data_dir.rglob("*.csv*")) if p.is_file()]
    return [p for p in files if first_line(p).startswith(TABLE1_HEADER_PREFIX)]


DST_YEARS = range(2018, 2035)  # last Sunday of March of each; matched against Datum, no year scan needed


def _dst_days(cfg: Config) -> dict[str, date]:
    return {
        _last_sunday_of_march(y).strftime(cfg.ingest.date_format): _last_sunday_of_march(y) for y in DST_YEARS
    }


def scan_table1_file(path: Path, cfg: Config) -> dict[str, Any]:
    """Everything check-data needs from one Table 1 file, in ONE streaming pass plus a 2000-row head.

    A 1.5 GB file is read once; nothing is materialised except the aggregates.
    """
    lf = _scan_csv(path, cfg.ingest.csv_separator)
    cols = lf.collect_schema().names()
    slot_map = {n: c for c in cols if (n := _normalize_slot(c)) is not None}
    slot_cols = list(slot_map.values())
    datum = pl.col("Datum").str.strip_chars()
    dst = _dst_days(cfg)
    on_dst = datum.is_in(list(dst))
    present = [s for s in DST_SLOTS if s in slot_map]
    aggs: list[pl.Expr] = [
        pl.len().alias("n"),
        datum.str.strptime(pl.Date, cfg.ingest.date_format, strict=False).min().alias("date_min"),
        datum.str.strptime(pl.Date, cfg.ingest.date_format, strict=False).max().alias("date_max"),
        on_dst.sum().alias("dst_rows"),
        datum.filter(on_dst).unique().alias("dst_days"),
        *[(_to_float(slot_map[s]).is_null() & on_dst).sum().alias(f"dst_null_{s}") for s in present],
    ]
    if slot_cols:
        is_null = [_to_float(c).is_null() for c in slot_cols]  # unparseable cells count as null
        aggs += [
            pl.sum_horizontal([e.cast(pl.UInt32) for e in is_null]).sum().alias("null_cells"),
            pl.any_horizontal(is_null).sum().alias("rows_with_null"),
        ]
    if "PLZ" in cols:
        aggs.append(pl.col("PLZ").str.strip_chars().unique().alias("plz"))
    stats = lf.group_by("OBIS-Code").agg(aggs).collect(engine="streaming")
    obis_counts = {str(k): int(v) for k, v in zip(stats["OBIS-Code"], stats["n"], strict=True)}
    dst_days = sorted({d for lst in stats["dst_days"] for d in lst}, key=lambda d: dst[d])
    plz: set[str] = set()
    if "plz" in stats.columns:
        plz = {str(v) for lst in stats["plz"] for v in lst if v is not None}
    daily_sums = pl.Series("daily_sum", [], pl.Float64)
    if slot_cols:
        daily_sums = (
            lf.filter(pl.col("OBIS-Code") == cfg.ingest.import_obis)
            .head(DAILY_SUM_SAMPLE_ROWS)
            .select(pl.sum_horizontal([_to_float(c) for c in slot_cols]).alias("daily_sum"))
            .collect()["daily_sum"]
        )
    return {
        "file": str(path),
        "rows": int(stats["n"].sum()),
        "n_slot_columns": len(slot_cols),
        "non_slot_columns": [c for c in cols if c not in slot_cols],
        "date_min": str(stats["date_min"].min()),
        "date_max": str(stats["date_max"].max()),
        "null_cells": int(stats["null_cells"].sum()) if "null_cells" in stats.columns else None,
        "rows_with_null": int(stats["rows_with_null"].sum()) if "rows_with_null" in stats.columns else None,
        "obis_counts": obis_counts,
        "plz": sorted(plz),
        "daily_sums": daily_sums,
        "dst_rows": int(stats["dst_rows"].sum()),
        "dst_days": dst_days,
        "dst_nulls": {s: int(stats[f"dst_null_{s}"].sum()) for s in present},
    }


def _check_table1(
    files: list[Path], cfg: Config, max_files: int, root: Path, scan: bool = True
) -> dict[str, Any]:
    per_year: dict[str, list[str]] = {}
    for p in files:
        per_year.setdefault(_year_of(p), []).append(
            str(p.relative_to(root)) if p.is_relative_to(root) else p.name
        )
    sampled = files[:max_files] if scan else []
    # the sampled files rarely contain March: files whose path looks like March are scanned for DST too
    dst_candidates = [f for f in files if f not in sampled and is_march_file(f, root)] if scan else []
    stats = {p: scan_table1_file(p, cfg) for p in [*sampled, *dst_candidates]}
    obis_counts: Counter[str] = Counter()
    plz_values: set[str] = set()
    sums: list[pl.Series] = []
    for p in sampled:
        st = stats[p]
        obis_counts.update(st["obis_counts"])
        plz_values |= set(st["plz"])
        sums.append(st["daily_sums"])
    all_sums = pl.concat(sums) if sums else pl.Series("daily_sum", [], pl.Float64)
    median = float(all_sums.median()) if all_sums.len() else None
    cells: dict[str, int] = dict.fromkeys(DST_SLOTS, 0)
    days_checked: list[str] = []
    files_checked: list[str] = []
    rows_on_dst_days = 0
    for p, st in stats.items():
        if st["dst_rows"] == 0:
            continue
        rows_on_dst_days += st["dst_rows"]
        files_checked.append(p.name)
        days_checked.extend(d for d in st["dst_days"] if d not in days_checked)
        for s, n in st["dst_nulls"].items():
            cells[s] += n
    sampled_info = [
        {k: v for k, v in stats[p].items() if k not in ("obis_counts", "plz", "daily_sums", "dst_nulls")}
        for p in sampled
    ]
    return {
        "files": {"count": len(files), "per_year": per_year, "sampled": sampled_info},
        "obis_counts": dict(sorted(obis_counts.items())),
        "unit_guess": "kwh_per_15min" if median is not None and median < KW_THRESHOLD_DAILY_SUM else "kw",
        "daily_sum_median": median,
        "daily_sum_quantiles": {
            q: (float(all_sums.quantile(float(q))) if all_sums.len() else None) for q in ("0.1", "0.5", "0.9")
        },
        "daily_sum_rows": int(all_sums.len()),
        "dst_null_cells": {
            **cells,
            "total": sum(cells.values()),
            "rows_on_dst_days": rows_on_dst_days,
            "days_checked": days_checked,
            "files_checked": files_checked,
        },
        "_plz_in_table1": sorted(plz_values),
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
            header = first_line(p)
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


def _check_registry(data_dir: Path, cfg: Config) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Registry report plus the key frames for the PLZ agreement check (None when a table is missing)."""
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
        return out, None
    t2, t3, t4 = tables["table2"], tables["table3"], tables["table4"]
    gp2, zp3, zp4, gp4 = (
        _has(t2.columns, "GP-Nr"),
        _has(t3.columns, "punktbezeichnung"),
        _has(t4.columns, "punktbezeichnung"),
        _has(t4.columns, "GPartner"),
    )
    mp3 = _has(t3.columns, "MP ID")
    out["keys"] = {
        "table2_gp": _key_pattern(t2[gp2]),
        "table3_meter": _key_pattern(t3[mp3]),
        "table3_zp": _key_pattern(t3[zp3]),
        "table4_zp": _key_pattern(t4[zp4]),
        "table4_gp": _key_pattern(t4[gp4]),
    }
    t3k = t3.select(meter=_raw_key(mp3), zp=_raw_key(zp3)).drop_nulls()
    t4k = t4.select(zp=_raw_key(zp4), gp=_raw_key(gp4)).drop_nulls().unique()
    out.update(_join_counts(t2.select(gp=_raw_key(gp2)), t3k, t4k))
    t4n = t4.select(zp=_raw_key(zp4), gp=_norm_key(gp4)).drop_nulls().unique()
    out["joined_with_normalized_keys"] = _join_counts(t2.select(gp=_norm_key(gp2)), t3k, t4n)
    # Table 2 cells may hold several GP numbers or text around them: pull every digit run of the
    # width Table 4 uses and join on those
    width = int(t4k["gp"].str.len_chars().mode()[0]) if t4k.height else 0
    if width:
        t2x = t2.select(gp=pl.col(gp2).cast(pl.String).str.extract_all(rf"\d{{{width}}}")).explode(
            "gp", empty_as_null=True
        )
        out["joined_with_extracted_keys"] = {"key_width": width, **_join_counts(t2x, t3k, t4k)}
    joined_gps = t4k.join(t3k, on="zp", how="semi")["gp"]
    t2_joined = t2.filter(_raw_key(gp2).is_in(joined_gps.to_list()))
    out["n_rows_table2_joined"] = t2_joined.height
    out["asset_counts"] = _asset_counts(t2)
    out["asset_counts_joined"] = _asset_counts(t2_joined)
    out["flag_values"] = _flag_values(t2, exclude=(gp2,))
    out["date_columns"] = _date_columns(t2)
    frames = {"t2": t2, "gp2": gp2, "plz2": _has(t2.columns, "PLZ"), "t3k": t3k, "t4k": t4k}
    return out, frames


def _flag_values(t2: pl.DataFrame, exclude: tuple[str, ...]) -> dict[str, dict[str, int]]:
    """Value vocabulary of low-cardinality string columns (ja/nein/blank …); no free text, no ids."""
    out: dict[str, dict[str, int]] = {}
    for col in t2.columns:
        s = t2[col]
        if col in exclude or s.dtype != pl.String or s.n_unique() > 12:
            continue
        if re.search(r"(?i)plz|^ort$|kanton|-nr|\bid\b", col):  # places and ids are not flags
            continue
        vc = s.str.strip_chars().value_counts().sort("count", descending=True)
        out[col] = {str(v): int(n) for v, n in vc.iter_rows()}
    return out


DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S")


def _date_columns(t2: pl.DataFrame) -> dict[str, Any]:
    """For every date-like column: how many rows are filled, which format parses them, min and max."""
    out: dict[str, Any] = {}
    for col in t2.columns:
        if not re.search(r"(?i)datum|übergabe|uebergabe|baustart|date", col):
            continue
        s = t2[col]
        info: dict[str, Any] = {"n_non_null": int(s.drop_nulls().len()), "dtype": str(s.dtype)}
        if s.dtype in (pl.Date, pl.Datetime):
            d = s.cast(pl.Date).drop_nulls()
        else:
            v = s.cast(pl.String).str.strip_chars().drop_nulls()
            v = v.filter(v != "")
            info["n_non_null"] = int(v.len())
            best, d = None, pl.Series([], dtype=pl.Date)
            for fmt in DATE_FORMATS:
                parsed = v.str.strptime(pl.Date, fmt, strict=False).drop_nulls()
                if parsed.len() > d.len():
                    best, d = fmt, parsed
            info["format"] = best
        info["n_parsed"] = int(d.len())
        info["min"], info["max"] = (str(d.min()), str(d.max())) if d.len() else (None, None)
        out[col] = info
    return out


def _plz_agreement(path: Path, frames: dict[str, Any], cfg: Config) -> dict[str, Any]:
    """Do joined meters sit in the PLZ Table 2 says? (guards against ids that match by accident)."""
    lf = _scan_csv(path, cfg.ingest.csv_separator)
    cols = lf.collect_schema().names()
    if "PLZ" not in cols or frames["plz2"] is None:
        return {"file": path.name, "skipped": "no PLZ column"}
    t1 = (
        lf.select(meter=pl.col("MP ID").str.strip_chars(), plz1=pl.col("PLZ").str.strip_chars())
        .unique()
        .collect(engine="streaming")
    )
    t2p = frames["t2"].select(gp=_raw_key(frames["gp2"]), plz2=_raw_key(frames["plz2"])).drop_nulls().unique()
    j = frames["t3k"].join(frames["t4k"], on="zp", how="inner").join(t2p, on="gp", how="inner")
    m = j.join(t1, on="meter", how="inner")
    agree = int((m["plz1"] == m["plz2"]).sum())
    return {
        "file": path.name,
        "n_meters_in_file": int(t1["meter"].n_unique()),
        "n_joined_meters_in_file": int(m["meter"].n_unique()),
        "n_plz_agree": agree,
        "n_plz_disagree": int(m.height - agree),
    }


def _raw_key(c: str) -> pl.Expr:
    return pl.col(c).cast(pl.String).str.strip_chars()


def _norm_key(c: str) -> pl.Expr:
    """Tolerant join key: whitespace stripped, Excel-style '.0' suffix and leading zeros removed."""
    return _raw_key(c).str.replace(r"\.0+$", "").str.replace(r"^0+(\d)", "${1}")


def _key_pattern(s: pl.Series) -> dict[str, Any]:
    """Shape of a join-key column without listing values: lengths, digits-only, zeros, '.0', separators."""
    v = s.cast(pl.String).str.strip_chars().drop_nulls()
    if v.len() == 0:
        return {"n": 0, "n_null": int(s.null_count())}
    lengths = v.str.len_chars()
    return {
        "n": int(v.len()),
        "n_unique": int(v.n_unique()),
        "n_null": int(s.null_count()),
        "len_hist": {str(k): int(n) for k, n in sorted(lengths.value_counts().iter_rows())},
        "all_digits": bool(v.str.contains(r"^\d+$").all()),
        "n_all_digits": int(v.str.contains(r"^\d+$").sum()),
        "with_leading_zero": int(v.str.starts_with("0").sum()),
        "with_decimal_suffix": int(v.str.contains(r"\.\d+$").sum()),
        "with_separator": int(v.str.contains(r"[\s/,;|&+-]").sum()),
        "with_non_ascii": int(v.str.contains(r"[^\x00-\x7F]").sum()),
    }


def _join_counts(t2k: pl.DataFrame, t3k: pl.DataFrame, t4k: pl.DataFrame) -> dict[str, Any]:
    """Table 3 (meter, zp) -> Table 4 (zp, gp) -> Table 2 (gp): counts at each step."""
    t2k = t2k.drop_nulls().unique()
    zp_hit = t3k.join(t4k, on="zp", how="inner")
    joined = zp_hit.join(t2k, on="gp", how="inner").unique(["meter", "gp"])
    per_gp = joined.group_by("gp").agg(pl.col("meter").n_unique().alias("n"))
    hist = {str(k): int(v) for k, v in sorted(per_gp["n"].value_counts().iter_rows())}
    return {
        "n_gp": t2k.height,
        "n_meters_table3": int(t3k["meter"].n_unique()),
        "n_meters_with_gp_in_table4": int(zp_hit["meter"].n_unique()),  # step 3->4
        "n_gp_table4": int(t4k["gp"].n_unique()),
        "n_gp_table4_in_table2": int(t4k.join(t2k, on="gp", how="semi")["gp"].n_unique()),  # step 4->2
        "n_meters_joined": int(joined["meter"].n_unique()),
        "n_gp_with_meter": int(joined["gp"].n_unique()),
        "n_gp_without_meter": int(t2k.height - joined["gp"].n_unique()),
        "meters_per_gp_hist": hist,
    }


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


WEATHER_TIME_COLS = ("timestamp_utc", "time", "timestamp", "datetime", "date")


def _parse_times(s: pl.Series) -> pl.Series:
    ts = s.str.strip_chars().str.to_datetime(time_unit="ms", strict=False)
    if ts.dtype.time_zone is not None:  # type: ignore[union-attr]
        ts = ts.dt.convert_time_zone("UTC").dt.replace_time_zone(None)
    return ts.drop_nulls()


def _check_weather(weather_dir: Path, plz_in_table1: list[str]) -> dict[str, Any]:
    files = find_weather_files(weather_dir)
    out: dict[str, Any] = {"dir": str(weather_dir), "n_files": len(files), "columns": []}
    out["parts"] = {
        d.name: {
            "success_marker": (d / "_SUCCESS.json").exists(),
            "metadata": (d / "metadata.json").exists(),
            "n_plz_dirs": len([q for q in (d / "hourly").glob("*") if q.is_dir()])
            if (d / "hourly").exists()
            else 0,
        }
        for d in sorted(weather_dir.glob("weather_part_*"))
        if d.is_dir()
    }
    files_per_plz: dict[str, list[Path]] = {}
    for p in files:
        plz = plz_of_weather_file(p, None)
        if plz is None:
            plz = plz_of_weather_file(p, read_raw(p))
        files_per_plz.setdefault(plz or "unknown", []).append(p)
    out["files_sample"] = [str(p.relative_to(weather_dir)) for p in files[:3]]
    if files:
        first = read_raw(files[0])
        out["columns"] = first.columns
        out["rows_first_file"] = first.height
        tcol = next((c for c in first.columns if c.lower() in WEATHER_TIME_COLS), None)
        out["time_column"] = tcol
        if tcol:
            sample = str(first[tcol][0]) if first.height else ""
            out["time_zone_hint"] = "utc" if "utc" in tcol.lower() or sample.endswith("Z") else "unknown"
            # continuity over every file of the first PLZ (months must chain without holes)
            first_plz = next(iter(files_per_plz))
            ts = pl.concat([_parse_times(read_raw(p)[tcol]) for p in files_per_plz[first_plz]]).sort()
            out["continuity_plz"] = first_plz
            out["continuity_files"] = len(files_per_plz[first_plz])
            out["time_min"], out["time_max"] = str(ts.min()), str(ts.max())
            out["hour_gaps"] = (
                int((ts.diff().drop_nulls() != timedelta(hours=1)).sum()) if ts.len() > 1 else 0
            )
            out["duplicate_hours"] = int(ts.len() - ts.n_unique())
    n_files = sorted(len(v) for v in files_per_plz.values())
    out["n_plz"] = len(files_per_plz)
    out["files_per_plz_min"] = n_files[0] if n_files else 0
    out["files_per_plz_max"] = n_files[-1] if n_files else 0
    out["plz_fewest_files"] = sorted(files_per_plz, key=lambda k: len(files_per_plz[k]))[:10]
    plz_with_weather = set(files_per_plz) - {"unknown"}
    out["plz_in_table1"] = sorted(plz_in_table1)
    out["plz_with_weather"] = sorted(plz_with_weather)
    out["plz_missing"] = sorted(set(plz_in_table1) - plz_with_weather)
    return out


# --------------------------------------------------------------------------- public


def run_check(
    data_dir: Path,
    weather_dir: Path,
    cfg: Config,
    max_files: int = 3,
    registry_dir: Path | None = None,
    scan_table1: bool = True,
) -> dict:
    """Measure Table 1 (sampled), the registry tables and the weather directory. Pure read-only.

    `registry_dir` defaults to `data_dir`; on Renku Tables 2-4 live on a different mount.
    """
    files = find_table1_files(data_dir)
    t1 = _check_table1(files, cfg, max_files, data_dir, scan=scan_table1)
    plz_in_table1 = t1.pop("_plz_in_table1")
    registry, frames = _check_registry(registry_dir or data_dir, cfg)
    plz_agreement: dict[str, Any] | None = None
    if scan_table1 and files and frames is not None:
        plz_agreement = _plz_agreement(files[-1], frames, cfg)
    return {
        "data_dir": str(data_dir),
        "registry_dir": str(registry_dir or data_dir),
        "config": {
            "import_obis": cfg.ingest.import_obis,
            "export_obis": cfg.ingest.export_obis,
            "unit_factor": cfg.ingest.unit_factor,
            "csv_separator": cfg.ingest.csv_separator,
            "date_format": cfg.ingest.date_format,
        },
        **t1,
        "registry": registry,
        "plz_agreement": plz_agreement,
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
