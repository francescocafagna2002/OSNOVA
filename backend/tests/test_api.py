# tests/test_api.py
import polars as pl
from fastapi.testclient import TestClient

from osnova.api.app import create_app
from osnova.config import Config
from osnova.export.build_json import build_buildings, write_buildings
from osnova.export.curate import pick_featured, pick_others
from osnova.io.lastgang import feature_dataset_path
from tests.test_export_json import _prepared_store


def _client(settings, synth_dir, truth) -> tuple[TestClient, list[dict]]:
    store, gp_of, preds = _prepared_store(settings, synth_dir, truth)
    featured = pick_featured(
        pl.read_parquet(feature_dataset_path(store)),
        preds,
        pl.read_parquet(store.showcase_path()),
        n=2,
        min_types=2,
        min_plz=1,
    )
    others = pick_others(list(gp_of.values()), featured, n=3, seed=0)
    write_buildings(store, build_buildings(store, Config(), featured, others))
    client = TestClient(create_app(store))
    return client, client.get("/buildings").json()


def test_health_and_list(settings, synth_dir, truth):
    client, buildings = _client(settings, synth_dir, truth)
    assert client.get("/health").json() == {"status": "ok", "buildings": len(buildings)}
    assert len(buildings) == 5 and buildings[0]["id"].startswith("AG-") and buildings[0]["featured"] is True


def test_one_building_and_404(settings, synth_dir, truth):
    client, buildings = _client(settings, synth_dir, truth)
    bid = buildings[0]["id"]
    assert client.get(f"/buildings/{bid}").json() == buildings[0]
    assert client.get("/buildings/AG-000000").status_code == 404


def test_profile_for_any_date(settings, synth_dir, truth):
    client, buildings = _client(settings, synth_dir, truth)
    bid = buildings[0]["id"]
    r = client.get(f"/buildings/{bid}/profile", params={"date": "2024-03-31"})
    assert r.status_code == 200
    body = r.json()
    assert body["profileDate"] == "2024-03-31" and len(body["electricity"]) == 96
    assert body["electricity"][0]["timestamp"] == "2024-03-31T00:00:00+01:00"
    assert isinstance(body["events"], list) and all(e["start"] >= "2024-03-30T18:00" for e in body["events"])
    assert client.get(f"/buildings/{bid}/profile", params={"date": "2021-01-01"}).status_code == 404
    assert client.get("/buildings/AG-000000/profile", params={"date": "2024-03-31"}).status_code == 404
    assert client.get(f"/buildings/{bid}/profile", params={"date": "not-a-date"}).status_code == 422


def test_cors_for_local_frontend(settings, synth_dir, truth):
    client, _ = _client(settings, synth_dir, truth)
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
