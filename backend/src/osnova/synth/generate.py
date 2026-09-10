# src/osnova/synth/generate.py
"""Write Tables 1-5 in the real file formats, with known injected assets, plus truth.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl

from osnova.io.store import WEATHER_VARS
from osnova.io.weather import upsample_15min
from osnova.synth.profiles import MeterSpec, simulate
from osnova.synth.weather import synth_weather

ORT = {"5000": "Aarau", "5400": "Baden", "5105": "Auenstein", "5200": "Brugg", "4800": "Zofingen"}
IMPORT_OBIS, EXPORT_OBIS = "1-1:1.29.0*255", "1-1:2.29.0*255"
SLOT_COLUMNS = [f"{(i // 4) % 24:02d}:{(i % 4) * 15:02d}" for i in range(1, 97)]  # 00:15 ... 23:45, 00:00


@dataclass(frozen=True)
class SynthSpec:
    meters: int = 40
    years: tuple[int, ...] = (2023, 2024)
    seed: int = 0
    plzs: tuple[str, ...] = ("5000", "5400", "5105", "5200", "4800")
    labeled_fraction: float = 0.5


def _draw_meters(spec: SynthSpec, rng: np.random.Generator) -> list[MeterSpec]:
    start = date(min(spec.years), 1, 1)
    end = date(max(spec.years), 12, 31)
    out: list[MeterSpec] = []
    n_labeled = int(spec.meters * spec.labeled_fraction)
    for i in range(spec.meters):
        labeled = i < n_labeled
        pv = rng.random() < (0.6 if labeled else 0.15)
        hp = rng.random() < (0.5 if labeled else 0.2)
        ev = rng.random() < (0.5 if labeled else 0.15)
        bat = pv and rng.random() < (0.4 if labeled else 0.3)
        if labeled and not (pv or hp or ev):
            pv = True  # registry rows always have at least one asset
        commissioned = None
        if labeled and rng.random() < 0.3:
            commissioned = start + timedelta(days=int(rng.integers(120, (end - start).days - 120)))
        out.append(
            MeterSpec(
                meter_id=10000 + i,
                gp_nr=500000 + i if labeled else None,
                plz=str(rng.choice(spec.plzs)),
                pv_kwp=float(rng.choice([4.0, 6.0, 8.0, 10.0])) if pv else 0.0,
                battery_kwh=float(rng.choice([5.0, 10.0])) if bat else 0.0,
                heat_pump=hp,
                ev_plateau_kw=float(rng.choice([3.7, 7.0, 11.0])) if ev else 0.0,
                commissioned_on=commissioned,
                has_export_row=pv or rng.random() < 0.2,
            )
        )
    return out


def _write_lastgang(
    out: Path, meters: list[MeterSpec], results: dict[int, tuple], ts: np.ndarray, spec: SynthSpec
) -> None:
    days = ts[::96].astype("datetime64[D]")
    for year in spec.years:
        for month in range(1, 13):
            mask = np.array([d.astype(object).year == year and d.astype(object).month == month for d in days])
            day_idx = np.flatnonzero(mask)
            rows: dict[str, list] = {"MP ID": [], "OBIS-Code": [], "Datum": [], "PLZ": []}
            values: list[np.ndarray] = []
            for m in meters:
                imp, exp = results[m.meter_id]
                for obis, arr in ((IMPORT_OBIS, imp), (EXPORT_OBIS, exp)):
                    if obis == EXPORT_OBIS and not m.has_export_row:
                        continue
                    for d in day_idx:
                        rows["MP ID"].append(m.meter_id)
                        rows["OBIS-Code"].append(obis)
                        rows["Datum"].append(days[d].astype(object).strftime("%d.%m.%Y"))
                        rows["PLZ"].append(m.plz)
                        values.append(arr[d * 96 : (d + 1) * 96] / 4.0)  # kW -> kWh per 15 min
            block = np.vstack(values)
            df = pl.DataFrame(rows).with_columns(
                [pl.Series(col, block[:, i].astype(np.float32)) for i, col in enumerate(SLOT_COLUMNS)]
            )
            path = (
                out
                / "aew-data"
                / "lastgang"
                / str(year)
                / f"{month:02d}"
                / f"lastgang_{year}_{month:02d}.csv"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            text = df.write_csv(separator=";", float_precision=3)
            path.write_text("\n".join(line + ";" for line in text.splitlines()) + "\n", encoding="utf-8")


def _write_registry(out: Path, meters: list[MeterSpec], rng: np.random.Generator) -> None:
    reg = out / "aew-data" / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    flag = lambda b: "ja" if b else None  # noqa: E731
    labeled = [m for m in meters if m.gp_nr is not None]
    t2 = pl.DataFrame(
        {
            "GP-Nr": [m.gp_nr for m in labeled],
            "PLZ": [m.plz for m in labeled],
            "Ort": [ORT.get(m.plz, m.plz) for m in labeled],
            "Kanton": ["AG"] * len(labeled),
            "WärmePumpe": [flag(m.heat_pump) for m in labeled],
            "PV": [flag(m.pv_kwp > 0) for m in labeled],
            "PV-Leistung in kWp": [m.pv_kwp or None for m in labeled],
            "Batterie/Speicher": [flag(m.battery_kwh > 0) for m in labeled],
            "Ladestation für EV": [flag(m.ev_plateau_kw > 0) for m in labeled],
            "Wärmepumpenboiler": [flag(rng.random() < 0.2) for _ in labeled],
            "Datum Unterschrift": [
                (m.commissioned_on - timedelta(days=90)) if m.commissioned_on else None for m in labeled
            ],
            "geplanter Baustart": [
                (m.commissioned_on - timedelta(days=30)) if m.commissioned_on else None for m in labeled
            ],
            "Übergabe": [m.commissioned_on for m in labeled],
            "InBetrieb-Datum": [m.commissioned_on for m in labeled],
        }
    )
    t2.write_excel(reg / "Table2_Buildings.xlsx")
    zp = {m.meter_id: f"CH{m.meter_id:031d}" for m in meters}
    pl.DataFrame(
        {"MP ID": [m.meter_id for m in meters], "Zählpunktbezeichnung": [zp[m.meter_id] for m in meters]}
    ).write_csv(reg / "Table3_MeterPoints.csv", separator=";")
    pl.DataFrame(
        {
            "Zählpunktbezeichnung": [zp[m.meter_id] for m in labeled],
            "GPartner": [m.gp_nr for m in labeled],
            "Anlage": [f"A{m.gp_nr}" for m in labeled],
        }
    ).write_csv(reg / "Table4_Installations.csv", separator=";")


def _write_weather(out: Path, weather: dict[str, pl.DataFrame]) -> None:
    (out / "weather").mkdir(parents=True, exist_ok=True)
    for plz, df in weather.items():
        meta = {
            "plz": plz,
            "latitude": 47.4,
            "longitude": 8.05,
            "elevation": 400.0,
            "utc_offset_seconds": 3600,
            "timezone": "Europe/Zurich",
            "timezone_abbreviation": "CET",
        }
        df.with_columns([pl.lit(v).alias(k) for k, v in meta.items()]).with_columns(
            time=pl.col("ts").dt.strftime("%Y-%m-%dT%H:%M")
        ).select([*meta, "time", *WEATHER_VARS]).write_csv(out / "weather" / f"open-meteo_{plz}.csv")


def generate(out: Path, spec: SynthSpec) -> dict:
    rng = np.random.default_rng(spec.seed)
    meters = _draw_meters(spec, rng)
    start, end = datetime(min(spec.years), 1, 1), datetime(max(spec.years), 12, 31, 23, 45)
    ts_series = pl.datetime_range(start, end, "15m", eager=True).cast(pl.Datetime("ms")).alias("ts")
    ts = ts_series.to_numpy().astype("datetime64[m]")
    weather = {plz: synth_weather(plz, spec.years, rng) for plz in spec.plzs}
    # hourly weather ends at 23:00, the 15-min grid at 23:45: pad the last three slots by forward fill
    grid = pl.DataFrame({"ts": ts_series})
    weather15 = {
        plz: grid.join(upsample_15min(w), on="ts", how="left").fill_null(strategy="forward")
        for plz, w in weather.items()
    }
    results: dict[int, tuple] = {}
    ev_sessions: dict[str, list] = {}
    for m in meters:
        w = weather15[m.plz]
        res = simulate(m, ts, w["temperature_2m"].to_numpy(), w["shortwave_radiation"].to_numpy(), rng)
        results[m.meter_id] = (res.import_kw, res.export_kw)
        ev_sessions[str(m.meter_id)] = [
            {"start": s["start"].isoformat(), "end": s["end"].isoformat(), "plateau_kw": s["plateau_kw"]}
            for s in res.ev_sessions
        ]
    _write_lastgang(out, meters, results, ts, spec)
    _write_registry(out, meters, rng)
    _write_weather(out, weather)
    truth = {
        "spec": asdict(spec),
        "meters": {
            str(m.meter_id): {
                "gp_nr": m.gp_nr,
                "plz": m.plz,
                "labeled": m.gp_nr is not None,
                "pv": m.pv_kwp > 0,
                "battery": m.battery_kwh > 0,
                "heat_pump": m.heat_pump,
                "ev": m.ev_plateau_kw > 0,
                "pv_kwp": m.pv_kwp,
                "battery_kwh": m.battery_kwh,
                "ev_plateau_kw": m.ev_plateau_kw,
                "commissioned_on": m.commissioned_on.isoformat() if m.commissioned_on else None,
                "has_export_row": m.has_export_row,
            }
            for m in meters
        },
        "ev_sessions": ev_sessions,
    }
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    return truth
