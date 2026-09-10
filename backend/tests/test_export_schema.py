# tests/test_export_schema.py
import json

import pytest
from pydantic import ValidationError

from osnova.export.schema import Building, BuildingsFile, to_fe_predictions

MINIMAL = {
    "id": "AG-000001",
    "postcode": "5000",
    "city": "Aarau",
    "canton": "AG",
    "predictions": {"pv": 92, "battery": 48, "heatPump": 31, "ev": 76},
    "electricity": [{"timestamp": "2025-06-18T00:00:00+02:00", "powerKw": -1.2}],
    "events": [
        {
            "type": "ev_charging",
            "start": "2025-06-18T22:15:00+02:00",
            "end": "2025-06-19T01:30:00+02:00",
            "confidence": 0.9,
        }
    ],
    "explanation": {
        "model": "LightGBM",
        "inputs": ["15-minute load profiles"],
        "additionalData": ["Open-Meteo"],
        "method": "SHAP",
        "methodDescription": "SHAP shows which features contributed most to the prediction.",
        "assets": {
            k: {"reasons": ["r"], "shap": [{"feature": "f", "contribution": 0.1}]}
            for k in ("pv", "battery", "heatPump", "ev")
        },
    },
}


def test_minimal_building_validates_and_defaults():
    b = Building.model_validate(MINIMAL)
    assert b.featured is False and b.history == [] and b.groundTruth is None


def test_rejects_unknown_event_type():
    bad = json.loads(json.dumps(MINIMAL))
    bad["events"][0]["type"] = "sauna"
    with pytest.raises(ValidationError):
        Building.model_validate(bad)


def test_probabilities_are_bounded_ints():
    bad = json.loads(json.dumps(MINIMAL))
    bad["predictions"]["pv"] = 101
    with pytest.raises(ValidationError):
        Building.model_validate(bad)


def test_to_fe_predictions_maps_keys_and_scales():
    p = to_fe_predictions({"pv": 0.923, "battery": 0.48, "heat_pump": 0.311, "ev": 0.76})
    assert p.model_dump() == {"pv": 92, "battery": 48, "heatPump": 31, "ev": 76}


def test_file_roundtrip():
    text = BuildingsFile.model_validate([MINIMAL]).model_dump_json()
    assert BuildingsFile.model_validate_json(text).root[0].id == "AG-000001"
