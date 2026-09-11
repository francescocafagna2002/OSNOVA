# src/osnova/api/app.py
"""Read-only FastAPI over the exported buildings.json plus per-date profiles from the building series."""

from __future__ import annotations

import json
from datetime import date

import polars as pl
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from osnova.export.build_json import electricity_for_day, events_for_day
from osnova.io.lastgang import gp_nr_expr, load_building_series, to_gp_nr
from osnova.io.store import EVENTS, Store

ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
ID_PREFIX = "AG-"
DATE_QUERY = Query(..., alias="date", description="YYYY-MM-DD, any day of the building series")


def _load_buildings(store: Store) -> list[dict]:
    path = store.buildings_json()
    return json.loads(path.read_text()) if path.exists() else []


def _load_events(store: Store) -> pl.DataFrame:
    path = store.events_path()
    if not path.exists():
        return pl.DataFrame(schema=EVENTS)
    return pl.read_parquet(path).with_columns(gp_nr=gp_nr_expr())


def _gp_nr_of(building_id: str) -> int | None:
    digits = building_id[len(ID_PREFIX) :] if building_id.startswith(ID_PREFIX) else building_id
    try:
        return to_gp_nr(digits)
    except ValueError:
        return None


def create_app(store: Store) -> FastAPI:
    app = FastAPI(title="OSNOVA prediction engine", version="0.1.0")
    app.add_middleware(
        CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET"], allow_headers=["*"]
    )
    buildings = _load_buildings(store)
    by_id = {b["id"]: b for b in buildings}
    events = _load_events(store)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "buildings": len(buildings)}

    @app.get("/buildings")
    def list_buildings() -> list[dict]:
        return buildings

    @app.get("/buildings/{building_id}")
    def one_building(building_id: str) -> dict:
        if building_id not in by_id:
            raise HTTPException(status_code=404, detail=f"unknown building {building_id}")
        return by_id[building_id]

    @app.get("/buildings/{building_id}/profile")
    def profile(building_id: str, day: date = DATE_QUERY) -> dict:
        gp_nr = _gp_nr_of(building_id)
        series = load_building_series(store, gp_nr) if gp_nr is not None else None
        if series is None or series.height == 0:
            raise HTTPException(status_code=404, detail=f"no series for {building_id}")
        day_rows = series.filter(pl.col("ts").dt.date() == day)
        if day_rows.height == 0:
            raise HTTPException(status_code=404, detail=f"no data for {building_id} on {day.isoformat()}")
        day_events = events.filter(pl.col("gp_nr") == gp_nr)
        return {
            "profileDate": day.isoformat(),
            "electricity": [p.model_dump() for p in electricity_for_day(day_rows, day)],
            "events": [e.model_dump() for e in events_for_day(day_events, day)],
        }

    return app
