# tests/conftest.py
import json
from pathlib import Path

import pytest

from osnova.config import Config, OsnovaSettings
from osnova.synth.generate import SynthSpec, generate


@pytest.fixture(scope="session")
def synth_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("synth")
    generate(out, SynthSpec(meters=24, years=(2023, 2024), seed=7))
    return out


@pytest.fixture(scope="session")
def truth(synth_dir: Path) -> dict:
    return json.loads((synth_dir / "truth.json").read_text())


@pytest.fixture
def settings(synth_dir: Path, tmp_path: Path) -> OsnovaSettings:
    return OsnovaSettings(
        data_dir=synth_dir / "aew-data", weather_dir=synth_dir / "weather", store_dir=tmp_path / "store"
    )


@pytest.fixture
def cfg() -> Config:
    return Config()
