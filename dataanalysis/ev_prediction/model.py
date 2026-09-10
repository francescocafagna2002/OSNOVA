from pathlib import Path
import json
import joblib


BASE_DIR = Path(__file__).resolve().parent

MODEL_DIR = BASE_DIR / "ev_model"


model = joblib.load(
    MODEL_DIR / "ev_model.joblib"
)


with open(
    MODEL_DIR / "ev_feature_columns.json",
    "r",
    encoding="utf-8"
) as f:
    feature_columns = json.load(f)