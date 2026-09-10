import joblib
import json

model = joblib.load(
    "../../store/models/pv_model.joblib"
)

with open(
    "../../store/models/pv_feature_columns.json",
    "r",
    encoding="utf-8"
) as f:
    feature_columns = json.load(f)