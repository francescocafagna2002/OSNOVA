# src/osnova/cli.py
"""osnova <stage> — one subcommand per pipeline stage. Stubs are replaced by the owning stream."""

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
def check_data(config: Path | None = ConfigOpt) -> None:
    """Measure facts about the real mount (OBIS codes, units, DST, joins, weather coverage)."""
    _stub("Stream A", "A1")


@app.command()
def registry(config: Path | None = ConfigOpt) -> None:
    """Tables 2-4 -> registry.parquet and cohort.parquet."""
    _stub("Stream A", "A2")


@app.command()
def ingest(
    config: Path | None = ConfigOpt, limit_files: int | None = typer.Option(None, "--limit-files")
) -> None:
    """Table 1 CSVs -> lastgang/bucket=NN/part.parquet for the cohort."""
    _stub("Stream A", "A3")


@app.command()
def weather(config: Path | None = ConfigOpt) -> None:
    """Open-Meteo CSVs -> weather/plz=XXXX.parquet."""
    _stub("Stream A", "A4")


@app.command()
def features(config: Path | None = ConfigOpt, workers: int = 4) -> None:
    """lastgang + weather -> features.parquet (one row per meter-year)."""
    _stub("Stream B", "B6")


@app.command()
def events(config: Path | None = ConfigOpt, workers: int = 4) -> None:
    """lastgang -> events.parquet + showcase.parquet."""
    _stub("Stream C", "C3")


@app.command()
def train(config: Path | None = ConfigOpt) -> None:
    """features + registry -> labels, models, predictions.parquet, metrics.json."""
    _stub("Stream D", "D2")


@app.command()
def export(config: Path | None = ConfigOpt, featured: int = 10, others: int = 200) -> None:
    """Everything -> export/buildings.json."""
    _stub("Stream C", "C4")


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the exported JSON over HTTP."""
    _stub("Stream C", "C7")


if __name__ == "__main__":
    app()
