# src/osnova/cli.py
"""osnova <stage> — one subcommand per pipeline stage. Stubs are replaced by the owning session.

registry / ingest / features are retired: feature_pipeline (scripts/build_feature_dataset.py) does
ingest + features at the building (gp_nr) grain.
"""

from __future__ import annotations

from pathlib import Path

import typer

from osnova.config import Config, OsnovaSettings, load_config

app = typer.Typer(no_args_is_help=True, help="OSNOVA prediction engine")
ConfigOpt = typer.Option(None, "--config", help="JSON file overriding config defaults")
OutOpt = typer.Option(..., "--out")
YearsOpt = typer.Option([2023, 2024], "--years")
FeaturesOpt = typer.Option(
    None, "--features", help="feature_dataset.parquet; default <store>/osnova/feature_output/"
)
DatesOpt = typer.Option(
    None,
    "--dates",
    help="GIGI dates parquet (gp_nr, commissioned_pv/ev/heatpump/battery); "
    "default <store>/osnova/feature_output/gigi_dates.parquet, skipped when absent",
)


def _ctx(config: Path | None) -> tuple[OsnovaSettings, Config]:
    return OsnovaSettings(), load_config(config)


def _stub(stream: str, card: str) -> None:
    typer.echo(f"not implemented: {stream} card {card}", err=False)
    raise typer.Exit(code=2)


FEATURE_PIPELINE_HINT = (
    "retired: ingest and features are done by feature_pipeline at the building (gp_nr) grain. "
    "Run `python3 scripts/build_feature_dataset.py --help` from backend/ "
    "(output: $OSNOVA_STORE_DIR/osnova/feature_output/feature_dataset.parquet)."
)


def _retired() -> None:
    typer.echo(FEATURE_PIPELINE_HINT)
    raise typer.Exit(code=2)


@app.command()
def synth(
    out: Path = OutOpt,
    meters: int = 40,
    years: list[int] = YearsOpt,
    seed: int = 0,
) -> None:
    """Generate synthetic Tables 1-5 in the real file formats (laptop development data)."""
    from osnova.synth.generate import SynthSpec, generate

    truth = generate(out, SynthSpec(meters=meters, years=tuple(years), seed=seed))
    typer.echo(f"wrote synthetic data for {len(truth['meters'])} meters to {out}")


@app.command("check-data")
def check_data(
    config: Path | None = ConfigOpt,
    max_files: int = typer.Option(3, "--max-files", help="Table 1 files to sample for OBIS/units/DST"),
    skip_table1: bool = typer.Option(False, "--skip-table1", help="only registry + weather (seconds)"),
) -> None:
    """Measure facts about the real mount (OBIS codes, units, DST, joins, weather coverage)."""
    import json
    import time

    from osnova.io.check_data import run_check, to_markdown
    from osnova.io.store import Store

    settings, cfg = _ctx(config)
    store = Store(settings)
    t0 = time.perf_counter()
    report = run_check(
        settings.data_dir,
        settings.weather_dir,
        cfg,
        max_files=max_files,
        registry_dir=settings.registry_root,
        scan_table1=not skip_table1,
    )
    out = store.data_check_json()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    store.write_manifest(
        "check_data",
        config=cfg.model_dump(),
        inputs={
            "data_dir": settings.data_dir,
            "registry_dir": settings.registry_root,
            "weather_dir": settings.weather_dir,
        },
        output=out,
        table1_files=report["files"]["count"],
        table1_sampled=len(report["files"]["sampled"]),
        duration_s=round(time.perf_counter() - t0, 1),
    )
    typer.echo(to_markdown(report))


@app.command()
def registry() -> None:
    """Retired: done by feature_pipeline (mapping.py, labels.py)."""
    _retired()


@app.command()
def ingest() -> None:
    """Retired: done by feature_pipeline (ingest.py)."""
    _retired()


@app.command()
def weather(config: Path | None = ConfigOpt) -> None:
    """Open-Meteo CSVs (ERA5 download layout, UTC) -> weather/plz=XXXX.parquet (local naive)."""
    import time

    from osnova.io.store import Store
    from osnova.io.weather import find_weather_files, group_files_by_plz, normalize_weather_all, write_weather

    settings, cfg = _ctx(config)
    store = Store(settings)
    t0 = time.perf_counter()
    files = find_weather_files(settings.weather_dir)
    if not files:
        typer.echo(f"no weather CSVs found under {settings.weather_dir}", err=True)
        raise typer.Exit(code=1)
    groups = group_files_by_plz(files)
    rows: dict[str, int] = {}
    spans: dict[str, list[str]] = {}
    for plz, plz_files in sorted(groups.items()):
        by_plz = normalize_weather_all(plz_files, cfg)
        rows.update(write_weather(store, by_plz))
        for p, df in by_plz.items():
            spans[p] = [str(df["ts"].min()), str(df["ts"].max())]
        typer.echo(f"plz={plz}: {len(plz_files)} files -> {rows.get(plz, 0)} hourly rows")
    store.write_manifest(
        "weather",
        config=cfg.model_dump(),
        inputs={"weather_dir": settings.weather_dir, "n_files": len(files)},
        output=store.weather_dir(),
        n_plz=len(rows),
        rows_per_plz=rows,
        span_per_plz=spans,
        duration_s=round(time.perf_counter() - t0, 1),
    )
    typer.echo(f"wrote {len(rows)} PLZ to {store.weather_dir()}")


@app.command()
def features() -> None:
    """Retired: done by feature_pipeline (features.py, pipeline.py), one row per gp_nr."""
    _retired()


@app.command()
def events(config: Path | None = ConfigOpt, workers: int = 4) -> None:
    """by_file building series -> events.parquet + showcase.parquet."""
    from osnova.events.run import run_events
    from osnova.io.store import Store

    settings, cfg = _ctx(config)
    store = Store(settings)
    ev, sc = run_events(store, cfg, workers=workers)
    by_type = dict(ev.group_by("type").len().sort("type").iter_rows()) if ev.height else {}
    typer.echo(f"{sc.height} buildings, {ev.height} events {by_type}")
    typer.echo(f"wrote {store.events_path()} and {store.showcase_path()}")


@app.command()
def train(
    config: Path | None = ConfigOpt,
    features: Path | None = FeaturesOpt,
    dates: Path | None = DatesOpt,
) -> None:
    """feature_dataset.parquet + GIGI dates -> labels.parquet, models/, predictions.parquet, metrics.json."""
    import time

    import polars as pl

    from osnova.io.store import Store
    from osnova.labels.build import build_labels
    from osnova.models.train import TRAIN_ORDER, train_all

    settings, cfg = _ctx(config)
    store = Store(settings)
    t0 = time.perf_counter()
    features_path = features or store.features_path()
    dates_path = dates or store.feature_output_dir() / "gigi_dates.parquet"
    if not features_path.exists():
        typer.echo(f"missing {features_path} (feature_dataset.parquet from feature_pipeline)", err=True)
        raise typer.Exit(code=1)
    table = pl.read_parquet(features_path).with_columns(pl.col("gp_nr").cast(pl.Int64, strict=False))
    n_bad_gp = table["gp_nr"].is_null().sum()
    table = table.filter(pl.col("gp_nr").is_not_null()).unique("gp_nr", keep="first").sort("gp_nr")
    gigi_dates = pl.read_parquet(dates_path) if dates_path.exists() else None
    if gigi_dates is None:
        typer.echo(f"no commissioning dates at {dates_path}: every flagged asset counts as visible")
    labels = build_labels(table, gigi_dates, cfg.labels)
    labels.write_parquet(store.labels_path())
    result = train_all(table, labels, cfg, store.models_dir())
    result.predictions.write_parquet(store.predictions_path())
    label_counts = {
        a: {
            "positive": labels.filter((pl.col("asset") == a) & (pl.col("label") == 1)).height,
            "registry_negative": labels.filter(
                (pl.col("asset") == a) & (pl.col("label") == 0) & (pl.col("source") == "registry")
            ).height,
            "unlabeled": labels.filter((pl.col("asset") == a) & (pl.col("source") == "unlabeled")).height,
        }
        for a in TRAIN_ORDER
    }
    store.write_manifest(
        "train",
        config=cfg.model_dump(),
        inputs={"features": features_path, "dates": dates_path if gigi_dates is not None else None},
        outputs={
            "labels": store.labels_path(),
            "predictions": store.predictions_path(),
            "models_dir": store.models_dir(),
        },
        n_buildings=table.height,
        n_dropped_gp_nr=int(n_bad_gp),
        labels=label_counts,
        registry_roc_auc={a: result.metrics[a]["registry"]["roc_auc"] for a in TRAIN_ORDER},
        duration_s=round(time.perf_counter() - t0, 1),
    )
    typer.echo(_metrics_table(result.metrics))
    typer.echo(f"wrote {result.predictions.height} predictions to {store.predictions_path()}")


def _metrics_table(metrics: dict) -> str:
    """Registry-row metrics per asset, model next to the rule baseline."""
    cols = ("n", "n_pos", "roc_auc", "pr_auc", "brier", "brier_calibrated", "precision_at_50", "recall_at_50")
    header = ["asset", *cols, "baseline_roc_auc"]
    lines = ["registry metrics (out-of-fold, source != unlabeled)", " | ".join(header)]

    def fmt(v: object) -> str:
        return f"{v:.3f}" if isinstance(v, float) else ("-" if v is None else str(v))

    for asset, m in metrics.items():
        reg = m["registry"]
        row = [asset, *(fmt(reg.get(c)) for c in cols), fmt(m["baseline"]["registry"].get("roc_auc"))]
        lines.append(" | ".join(row))
    return "\n".join(lines)


@app.command()
def export(
    config: Path | None = ConfigOpt,
    featured: int = 10,
    others: int = 200,
    min_types: int = typer.Option(
        3, "--min-types", help="featured: distinct event types on the showcase day"
    ),
    min_plz: int = typer.Option(5, "--min-plz", help="featured: warn when spread over fewer PLZ"),
    recurate: bool = typer.Option(False, "--recurate", help="ignore export/featured.json and pick again"),
) -> None:
    """predictions + showcase + events + building series -> export/buildings.json (+ featured.json)."""
    import time

    import polars as pl

    from osnova.export.build_json import build_buildings, load_featured, load_labels, write_buildings
    from osnova.export.curate import pick_featured, pick_others
    from osnova.io.lastgang import list_buildings
    from osnova.io.store import Store

    settings, cfg = _ctx(config)
    store = Store(settings)
    t0 = time.perf_counter()
    pinned = None if recurate else load_featured(store)
    if pinned is not None:
        featured_ids, other_ids = pinned
        typer.echo(f"reusing {store.featured_json()}")
    else:
        labels = load_labels(store)
        featured_ids = pick_featured(
            labels if labels is not None else pl.DataFrame({"gp_nr": []}, schema={"gp_nr": pl.String}),
            pl.read_parquet(store.predictions_path()),
            pl.read_parquet(store.showcase_path()),
            n=featured,
            min_types=min_types,
            min_plz=min_plz,
        )
        other_ids = pick_others(list_buildings(store), featured_ids, n=others, seed=cfg.cohort.seed)
    buildings = build_buildings(store, cfg, featured_ids, other_ids)
    path = write_buildings(store, buildings)
    n_featured = sum(b.featured for b in buildings)
    store.write_manifest(
        "export",
        config=cfg.model_dump(),
        inputs={
            "predictions": store.predictions_path(),
            "showcase": store.showcase_path(),
            "events": store.events_path(),
            "registry": store.registry_path(),
        },
        output=path,
        n_buildings=len(buildings),
        n_featured=n_featured,
        featured=featured_ids,
        duration_s=round(time.perf_counter() - t0, 1),
    )
    typer.echo(f"featured: {', '.join(map(str, featured_ids)) or '(none)'}")
    typer.echo(f"wrote {len(buildings)} buildings ({n_featured} featured) to {path}")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve export/buildings.json and per-date profiles over HTTP (GET /health, /buildings, ...)."""
    import uvicorn

    from osnova.api.app import create_app
    from osnova.io.store import Store

    settings, _ = _ctx(None)
    uvicorn.run(create_app(Store(settings)), host=host, port=port)


if __name__ == "__main__":
    app()
