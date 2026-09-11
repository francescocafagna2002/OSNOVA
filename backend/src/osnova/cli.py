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
    """Building series (feature_output/intermediate) -> events.parquet + showcase.parquet."""
    _stub("Session 3", "C3")


@app.command()
def train(config: Path | None = ConfigOpt) -> None:
    """feature_dataset.parquet -> labels, models, predictions.parquet, metrics.json."""
    _stub("Session 2", "D2")


@app.command()
def export(config: Path | None = ConfigOpt, featured: int = 10, others: int = 200) -> None:
    """Everything -> export/buildings.json (id = AG-{gp_nr})."""
    _stub("Session 3", "C4")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the exported JSON over HTTP."""
    _stub("Session 3", "C7")


if __name__ == "__main__":
    app()
