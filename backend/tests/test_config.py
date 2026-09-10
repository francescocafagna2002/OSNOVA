# tests/test_config.py
import json
from pathlib import Path

from osnova.config import Config, OsnovaSettings, load_config


def test_settings_read_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("OSNOVA_STORE_DIR", str(tmp_path / "store"))
    s = OsnovaSettings()
    assert s.store_dir == tmp_path / "store"
    assert s.out == tmp_path / "store" / "osnova"


def test_defaults_match_spec():
    cfg = Config()
    assert cfg.ingest.unit_factor == 4.0
    assert cfg.features.min_days == 300
    assert cfg.features.ev_thresholds_kw == (3.0, 5.0, 7.0, 11.0)
    assert cfg.events.ev_residual_kw == 2.5
    assert cfg.labels.unlabeled_weight == 0.5
    assert cfg.cohort.unlabeled_sample == 3000
    assert cfg.weather.timezone == "Europe/Zurich" and cfg.weather.utc_time_column == "timestamp_utc"


def test_load_config_overrides(tmp_path: Path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps({"ingest": {"unit_factor": 1.0}}))
    cfg = load_config(p)
    assert cfg.ingest.unit_factor == 1.0
    assert cfg.features.min_days == 300
