# src/osnova/synth/profiles.py
"""Simulate one meter's 15-minute import/export from a base load plus injected assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np


@dataclass(frozen=True)
class MeterSpec:
    meter_id: int
    gp_nr: int | None
    plz: str
    pv_kwp: float = 0.0  # 0 = no PV
    battery_kwh: float = 0.0  # 0 = no battery
    heat_pump: bool = False
    ev_plateau_kw: float = 0.0  # 0 = no EV
    commissioned_on: date | None = None  # assets active only from this date; None = always
    has_export_row: bool = False


@dataclass
class SimResult:
    import_kw: np.ndarray
    export_kw: np.ndarray
    ev_sessions: list[dict] = field(
        default_factory=list
    )  # {"start": datetime, "end": datetime, "plateau_kw": float}


def _bell(x: np.ndarray, center: float, width: float) -> np.ndarray:
    return np.exp(-((x - center) ** 2) / (2 * width * width))


def simulate(
    spec: MeterSpec, ts: np.ndarray, temperature: np.ndarray, shortwave: np.ndarray, rng: np.random.Generator
) -> SimResult:
    """ts: datetime64[m] 15-minute grid; temperature/shortwave: same length (already 15-min)."""
    n = len(ts)
    ts_py = ts.astype("datetime64[s]").astype(datetime)
    hour_f = np.array([t.hour + t.minute / 60 for t in ts_py])
    weekend = np.array([t.weekday() >= 5 for t in ts_py])
    active = np.ones(n, dtype=bool)
    if spec.commissioned_on is not None:
        active = ts >= np.datetime64(spec.commissioned_on)

    base = 0.3 + 0.1 * rng.random(n) + 0.6 * _bell(hour_f, 7.5, 1.0) + 1.0 * _bell(hour_f, 19.0, 1.5)
    base *= np.where(weekend & (hour_f > 9) & (hour_f < 18), 1.15, 1.0)

    hp = np.zeros(n)
    if spec.heat_pump:
        hdd = np.clip(15.0 - temperature, 0, None)
        cycling = ((np.arange(n) // 2) % 2).astype(float)  # 30 min on, 30 min off
        hp = 0.25 * hdd * (0.7 + 0.6 * cycling) * active

    ev = np.zeros(n)
    sessions: list[dict] = []
    if spec.ev_plateau_kw > 0:
        n_weeks = n // (96 * 7)
        for week in range(n_weeks):
            for _ in range(rng.integers(2, 5)):
                day = rng.integers(0, 7)
                start = week * 96 * 7 + day * 96 + int(round(rng.normal(21.5, 1.2) * 4))
                duration = int(rng.integers(6, 17))
                end = min(start + duration, n)
                if start < 0 or start >= n or not active[start]:
                    continue
                ev[start:end] = spec.ev_plateau_kw + rng.normal(0, 0.1, end - start)
                sessions.append(
                    {"start": ts_py[start], "end": ts_py[min(end, n - 1)], "plateau_kw": spec.ev_plateau_kw}
                )

    load = base + hp + ev
    gen = spec.pv_kwp * shortwave / 1000.0 * 0.85 * active if spec.pv_kwp > 0 else np.zeros(n)
    net = load - gen

    if spec.battery_kwh > 0:
        soc, p_max, charge, discharge = 0.0, spec.battery_kwh / 2, np.zeros(n), np.zeros(n)
        for i in range(n):
            if not active[i]:
                continue
            if net[i] < 0:
                c = min(-net[i], p_max, (spec.battery_kwh - soc) * 4)
                charge[i], soc = c, soc + c / 4
            elif soc > 0:
                d = min(net[i], p_max, soc * 4)
                discharge[i], soc = d, soc - d / 4
        net = net + charge - discharge

    return SimResult(
        import_kw=np.clip(net, 0, None).astype(np.float32),
        export_kw=np.clip(-net, 0, None).astype(np.float32),
        ev_sessions=sessions,
    )
