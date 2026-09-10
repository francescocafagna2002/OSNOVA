import joblib
import json

model = joblib.load(
    "pv_model/pv_model.joblib"
)

with open(
    "pv_model/pv_feature_columns.json",
    "r",
    encoding="utf-8"
) as f:
    feature_columns = json.load(f)