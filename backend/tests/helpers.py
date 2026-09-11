# tests/helpers.py
"""Shared helpers for tests on synthetic data."""

from __future__ import annotations


def pick(truth: dict, *, always_active: bool = True, **assets: bool) -> int:
    """First synth meter whose truth flags match `assets` (e.g. ev=True, pv=False).

    always_active=True prefers meters without a commissioning date, so injected assets
    are present over the whole series.
    """
    matches = []
    for mid, t in truth["meters"].items():
        if all(bool(t[k]) == v for k, v in assets.items()):
            matches.append((t["commissioned_on"] is not None, int(mid)))
    if not matches:
        raise LookupError(f"no synth meter with {assets}")
    matches.sort()
    if always_active and matches[0][0]:
        raise LookupError(f"no always-active synth meter with {assets}")
    return matches[0][1]


# --------------------------------------------------------------------------- synth -> pipeline frames


def meter_year(synth_dir, meter_id: int, year: int, cfg=None):
    """MeterYear of one synth meter, with calendar and weather columns, like the features stage builds."""
    from osnova.config import FeatureConfig
    from osnova.features.base import make_meter_year
    from osnova.synth.loader import load_synth_meter, load_synth_weather

    lg = load_synth_meter(synth_dir, meter_id, year)
    return make_meter_year(lg, load_synth_weather(synth_dir, str(lg["plz"][0])), cfg or FeatureConfig())


def synth_gp_nr(truth: dict, meter_id: int) -> int:
    """gp_nr of a synth meter; unlabeled meters get a fake 9xxxxx building id."""
    gp = truth["meters"][str(meter_id)]["gp_nr"]
    return int(gp) if gp is not None else int(f"9{meter_id:05d}")


def write_synth_by_file(
    synth_dir, store, truth: dict, years=(2023, 2024), *, legacy_power_kw: bool = False
) -> dict[int, int]:
    """Write the synth lastgang in the feature_pipeline by_file layout (one Parquet per source file).

    Revised 2026-09-11 layout: gp_nr (i64), ts (Datetime us, local naive, interval start), plz (str),
    import_kw, export_kw, net_kw (f32, net negative = export), num_mp_with_data (i32).
    legacy_power_kw=True writes the pre-revision layout (gp_nr str, power_kw f64 net) instead.
    Returns {meter_id: gp_nr}.
    """
    import polars as pl

    from osnova.io.lastgang import by_file_dir
    from osnova.synth.generate import EXPORT_OBIS, IMPORT_OBIS, SLOT_COLUMNS

    gp_of = {int(m): synth_gp_nr(truth, int(m)) for m in truth["meters"]}
    idx = {s: i for i, s in enumerate(SLOT_COLUMNS)}
    out_dir = by_file_dir(store)
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in years:
        for f in sorted((synth_dir / "aew-data" / "lastgang" / str(year)).rglob("*.csv")):
            wide = pl.read_csv(
                f,
                separator=";",
                truncate_ragged_lines=True,
                schema_overrides={
                    "MP ID": pl.Int64,
                    "PLZ": pl.String,
                    **{s: pl.Float32 for s in SLOT_COLUMNS},
                },
            ).select(["MP ID", "OBIS-Code", "Datum", "PLZ", *SLOT_COLUMNS])
            long = (
                wide.unpivot(
                    index=["MP ID", "OBIS-Code", "Datum", "PLZ"], on=SLOT_COLUMNS, variable_name="slot"
                )
                .with_columns(
                    ts=pl.col("Datum").str.to_date("%d.%m.%Y").cast(pl.Datetime("us"))
                    + pl.duration(minutes=pl.col("slot").replace_strict(idx, return_dtype=pl.Int32) * 15),
                    signed=pl.when(pl.col("OBIS-Code") == IMPORT_OBIS)
                    .then(pl.col("value"))
                    .when(pl.col("OBIS-Code") == EXPORT_OBIS)
                    .then(-pl.col("value"))
                    .otherwise(None)
                    * 4.0,
                )
                .group_by(["MP ID", "ts"])
                .agg(
                    power_kw=pl.col("signed").sum().cast(pl.Float64),
                    import_kw=pl.col("signed").filter(pl.col("signed") > 0).sum().cast(pl.Float32),
                    export_kw=(-pl.col("signed").filter(pl.col("signed") < 0).sum()).cast(pl.Float32),
                    plz=pl.col("PLZ").first(),
                )
                .with_columns(
                    gp_nr=pl.col("MP ID").replace_strict(gp_of, return_dtype=pl.Int64),
                    net_kw=pl.col("power_kw").cast(pl.Float32),
                )
                .sort(["gp_nr", "ts"])
            )
            if legacy_power_kw:
                long = long.select(
                    pl.col("gp_nr").cast(pl.String),
                    "ts",
                    "power_kw",
                    "plz",
                    pl.lit(1, dtype=pl.UInt32).alias("num_mp_with_data"),
                )
            else:
                long = long.select(
                    "gp_nr",
                    "ts",
                    "plz",
                    "import_kw",
                    "export_kw",
                    "net_kw",
                    pl.lit(1, dtype=pl.Int32).alias("num_mp_with_data"),
                )
            long.write_parquet(out_dir / f"{f.stem}.parquet")
    return gp_of


def write_synth_feature_dataset(store, truth: dict) -> None:
    """feature_dataset.parquet with the label columns the exporter reads (1/0 labeled, null unlabeled)."""
    import polars as pl

    from osnova.io.lastgang import feature_dataset_path

    rows = []
    for m, t in truth["meters"].items():
        lab = t["labeled"]
        rows.append(
            {
                "gp_nr": synth_gp_nr(truth, int(m)),
                "plz": t["plz"],
                "num_mp_ids": 1,
                "sessions_per_week": 3.0 if t["ev"] else 0.2,
                "session_median": t["ev_plateau_kw"] if t["ev"] else 0.0,
                "p99_consumption": 8.0 if t["ev"] else 2.5,
                "total_export_kwh": 4000.0 if t["pv"] else 0.0,
                "days_with_export_ratio": 0.8 if t["pv"] else 0.0,
                "label_pv": int(t["pv"]) if lab else None,
                "label_ev": int(t["ev"]) if lab else None,
                "label_heatpump": int(t["heat_pump"]) if lab else None,
                "label_battery": int(t["battery"]) if lab else None,
            }
        )
    path = feature_dataset_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(rows).cast(
        {c: pl.Int8 for c in ("label_pv", "label_ev", "label_heatpump", "label_battery")}
    ).write_parquet(path)


def write_synth_weather(synth_dir, store) -> None:
    """weather/plz=XXXX.parquet for every synth PLZ, via the weather stage's normaliser."""
    from osnova.config import Config
    from osnova.io.weather import find_weather_files, normalize_weather_all, write_weather

    write_weather(store, normalize_weather_all(find_weather_files(synth_dir / "weather"), Config()))
