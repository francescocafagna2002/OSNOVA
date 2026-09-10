"""Building-level feature extraction pipeline for the Energy Fingerprints hackathon.

Raw 15-minute smart-meter consumption + MP->building mappings + hourly weather
-> one row per GP-Nr (building) in ``feature_dataset.parquet``.

See ``backend/feature_pipeline/README.md`` for the full description and
``scripts/build_feature_dataset.py`` for the CLI entrypoint.

No model training, SHAP, or UI lives here by design — this package only
computes and stores features.
"""
