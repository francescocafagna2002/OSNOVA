# src/osnova/events/run.py
"""The `events` stage: detectors per building over the by_file series -> events.parquet, showcase.parquet."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor

import polars as pl

from osnova.config import Config, OsnovaSettings
from osnova.events.ev_sessions import detect_ev_sessions
from osnova.events.high_load import detect_high_load
from osnova.events.pv_windows import WINDOW_SCHEMA, detect_pv_windows, empty_windows
from osnova.events.showcase import last_full_day, pick_showcase_day
from osnova.io.lastgang import list_buildings, load_building_chunk
from osnova.io.store import EVENTS, SHOWCASE, Store
from osnova.io.weather import load_weather, upsample_15min

BUILDINGS_PER_SCAN = 32  # buildings loaded per by_file scan; one scan per worker task

# A detector maps the building frame to WINDOW_SCHEMA rows (start, end, confidence, peak_kw, energy_kwh).
Detector = Callable[[pl.DataFrame, Config], pl.DataFrame]


def _ev(df: pl.DataFrame, cfg: Config) -> pl.DataFrame:
    s = detect_ev_sessions(df["ts"].to_numpy(), df["import_kw"].to_numpy(), cfg.events)
    return s.select("start", "end", "confidence", pl.col("plateau_kw").alias("peak_kw"), "energy_kwh").cast(
        dict(WINDOW_SCHEMA)
    )


def _pv(df: pl.DataFrame, cfg: Config) -> pl.DataFrame:
    return detect_pv_windows(df, night_baseline_kw(df, cfg), cfg.events)


def night_baseline_kw(df: pl.DataFrame, cfg: Config) -> float:
    lo, hi = cfg.features.night
    h = df["ts"].dt.hour()
    night = df.filter((h >= lo) & (h < hi) & (pl.col("quality") == "ok"))["import_kw"]
    v = night.median() if night.len() else None
    return float(v) if v is not None else 0.0


DETECTORS: list[tuple[str, Detector]] = [("ev_charging", _ev), ("pv_generation", _pv)]


def building_frame(series: pl.DataFrame, weather_hourly: pl.DataFrame | None) -> pl.DataFrame:
    """BUILDING_SERIES rows + weather columns (15-min upsampled) when available."""
    if weather_hourly is None or weather_hourly.height == 0:
        return series.with_columns(
            shortwave_radiation=pl.lit(None, pl.Float32), is_sunny_day=pl.lit(None, pl.Boolean)
        )
    w = upsample_15min(weather_hourly).select("ts", "shortwave_radiation", "temperature_2m", "is_sunny_day")
    return series.join(w, on="ts", how="left")


def events_for_building(gp_nr: str, frame: pl.DataFrame, cfg: Config) -> pl.DataFrame:
    """All detectors, then the high-load fallback on what is left. EVENTS schema."""
    if frame.height == 0:
        return pl.DataFrame(schema=EVENTS)
    parts = []
    for name, fn in DETECTORS:
        out = fn(frame, cfg)
        parts.append(out.with_columns(type=pl.lit(name)))
    claimed = pl.concat([p.select("start", "end") for p in parts]) if parts else empty_windows()
    parts.append(detect_high_load(frame, claimed, cfg.events).with_columns(type=pl.lit("high_consumption")))
    return (
        pl.concat(parts)
        .with_columns(gp_nr=pl.lit(gp_nr))
        .select(list(EVENTS.keys()))
        .cast(dict(EVENTS))
        .sort("start")
    )


def showcase_for_building(gp_nr: str, series: pl.DataFrame, events: pl.DataFrame, cfg: Config) -> dict:
    picked = pick_showcase_day(events, cfg.events)
    if picked is None:
        return {"gp_nr": gp_nr, "showcase_date": last_full_day(series), "n_event_types": 0}
    return {"gp_nr": gp_nr, "showcase_date": picked[0], "n_event_types": picked[1]}


def process_chunk(
    settings: OsnovaSettings, gp_nrs: list[str], cfg: Config
) -> tuple[pl.DataFrame, pl.DataFrame]:
    store = Store(settings)
    series_by_gp = load_building_chunk(store, gp_nrs)
    weather_cache: dict[str, pl.DataFrame | None] = {}
    ev_parts: list[pl.DataFrame] = []
    sc_rows: list[dict] = []
    for gp, series in series_by_gp.items():
        plz = series["plz"].drop_nulls().first() if series.height else None
        if plz is not None and plz not in weather_cache:
            weather_cache[plz] = load_weather(store, str(plz))
        frame = building_frame(series, weather_cache.get(plz) if plz is not None else None)
        ev = events_for_building(gp, frame, cfg)
        ev_parts.append(ev)
        sc_rows.append(showcase_for_building(gp, series, ev, cfg))
    events = pl.concat(ev_parts) if ev_parts else pl.DataFrame(schema=EVENTS)
    showcase = pl.DataFrame(sc_rows, schema=SHOWCASE) if sc_rows else pl.DataFrame(schema=SHOWCASE)
    return events, showcase


def run_events(store: Store, cfg: Config, workers: int = 4) -> tuple[pl.DataFrame, pl.DataFrame]:
    """events.parquet + showcase.parquet for every building in the by_file Parquet."""
    t0 = time.perf_counter()
    buildings = list_buildings(store)
    chunks = [buildings[i : i + BUILDINGS_PER_SCAN] for i in range(0, len(buildings), BUILDINGS_PER_SCAN)]
    if workers > 1 and len(chunks) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(
                pool.map(process_chunk, [store.settings] * len(chunks), chunks, [cfg] * len(chunks))
            )
    else:
        results = [process_chunk(store.settings, c, cfg) for c in chunks]
    events = pl.concat([r[0] for r in results]) if results else pl.DataFrame(schema=EVENTS)
    showcase = pl.concat([r[1] for r in results]) if results else pl.DataFrame(schema=SHOWCASE)
    events = events.sort(["gp_nr", "start"])
    showcase = showcase.sort("gp_nr")
    store.root.mkdir(parents=True, exist_ok=True)
    events.write_parquet(store.events_path())
    showcase.write_parquet(store.showcase_path())
    store.write_manifest(
        "events",
        config=cfg.model_dump(),
        inputs={"by_file_dir": str(store.root / "feature_output" / "intermediate" / "by_file")},
        outputs={"events": store.events_path(), "showcase": store.showcase_path()},
        n_buildings=len(buildings),
        n_events=events.height,
        events_by_type=dict(events.group_by("type").len().iter_rows()) if events.height else {},
        duration_s=round(time.perf_counter() - t0, 1),
    )
    return events, showcase
