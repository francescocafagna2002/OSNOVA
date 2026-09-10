#!/usr/bin/env python3
"""Generate a small synthetic input set in the *real* file formats/schemas.

There is no real AEW data on this machine (only Renku has it — see
``backend/CLAUDE.md``), so this is what ``build_feature_dataset.py`` is
validated against locally: consumption CSVs, the two mapping CSVs, the GIGI
label CSV and per-PLZ weather CSVs, all shaped exactly like the real files
the brief describes, with known devices injected so the pipeline output can
be sanity-checked (e.g. a PV building should show a strongly negative
``correlation_solar_radiation_consumption``).

This script is dev/test tooling only — it is not part of the feature
pipeline itself and produces no ML labels beyond what it injects.

Usage:
    python3 scripts/make_synth_fixture.py --out data/synth_input --buildings 100 --days 60
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import date, datetime, timedelta
from pathlib import Path

QUARTER_LABELS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
# Real file order per the brief: 00:15, 00:30, ..., 23:45, then 00:00 last.
CSV_COLUMN_ORDER = QUARTER_LABELS[1:] + QUARTER_LABELS[:1]

PLZ_POOL = ["5000", "5200", "5400", "8000", "4600"]
DEVICE_PROFILES = ["baseline", "pv", "ev", "heatpump", "battery", "pv_ev", "pv_battery"]


def daterange(start: date, days: int):
    for i in range(days):
        yield start + timedelta(days=i)


def seasonal_temp(d: date, rng: random.Random) -> float:
    day_of_year = d.timetuple().tm_yday
    seasonal = 8 + 14 * math.sin(2 * math.pi * (day_of_year - 80) / 365)
    return seasonal + rng.gauss(0, 2)


def hourly_temp(base_temp: float, hour: int, rng: random.Random) -> float:
    diurnal = 4 * math.sin(2 * math.pi * (hour - 9) / 24)
    return base_temp + diurnal + rng.gauss(0, 0.5)


def clear_sky_radiation(hour: int, minute: int, cloud_factor: float, month: int) -> float:
    t = hour + minute / 60.0
    if t < 6 or t > 20:
        return 0.0
    seasonal_scale = 0.4 + 0.6 * (1 - abs(month - 6.5) / 6.5)
    bell = math.sin(math.pi * (t - 6) / 14) ** 2
    return max(0.0, 900 * seasonal_scale * bell * cloud_factor)


def build_weather_lookup(plz_list, start, days, seed):
    """Deterministic per-(plz, date) hourly weather, keyed by plz then date.

    Built once and reused both for the weather CSVs and for injecting the
    matching PV/heat-pump correlation into synthetic consumption, so the two
    actually agree (otherwise the correlation features would validate
    against noise instead of the injected signal).
    """
    lookup: dict[tuple[str, date], dict[int, dict]] = {}
    for plz in plz_list:
        rng_w = random.Random(hash((seed, plz)) & 0xFFFFFFFF)
        for d in daterange(start, days):
            base_temp = seasonal_temp(d, rng_w)
            cloud_factor = rng_w.uniform(0.25, 1.0)
            hours = {}
            for hour in range(24):
                temp = hourly_temp(base_temp, hour, rng_w)
                radiation = clear_sky_radiation(hour, 0, cloud_factor, d.month)
                sunshine = min(3600.0, radiation / 900.0 * 3600.0) if radiation > 50 else 0.0
                hours[hour] = {
                    "temperature_2m": round(temp, 2),
                    "relative_humidity_2m": round(rng_w.uniform(40, 95), 1),
                    "precipitation": round(max(0, rng_w.gauss(0.2, 0.5)), 2),
                    "snowfall": 0.0,
                    "cloud_cover": round((1 - cloud_factor) * 100, 1),
                    "wind_speed_10m": round(rng_w.uniform(0, 15), 1),
                    "shortwave_radiation": round(radiation, 1),
                    "direct_radiation": round(radiation * 0.7, 1),
                    "diffuse_radiation": round(radiation * 0.3, 1),
                    "sunshine_duration": round(sunshine, 0),
                }
            lookup[(plz, d)] = hours
    return lookup


def make_weather(plz_list, start, days, weather_lookup, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for plz in plz_list:
        rows = []
        for d in daterange(start, days):
            for hour in range(24):
                ts = datetime(d.year, d.month, d.day, hour, 0)
                row = {"time": ts.strftime("%Y-%m-%dT%H:%M")}
                row.update(weather_lookup[(plz, d)][hour])
                rows.append(row)
        path = out_dir / f"weather_{plz}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), delimiter=",")
            writer.writeheader()
            writer.writerows(rows)


def make_labels(buildings, out_path: Path, rng: random.Random) -> None:
    header = [
        "GP-Nr", "PLZ", "Ort", "Kanton", "WärmePumpe", "PV", "PV-Leistung in kWp",
        "Batterie/Speicher", "Ladestation für Elektrofahrzeuge", "Wärmepumpenboiler",
        "Datum Unterschrift", "geplanter Baustart", "Übergabe", "InBetrieb-Datum",
    ]
    rows = []
    for b in buildings:
        if not b["labeled"]:
            continue
        profile = b["profile"]
        has_pv = "pv" in profile
        has_ev = "ev" in profile
        has_hp = profile == "heatpump"
        has_batt = "battery" in profile
        rows.append(
            {
                "GP-Nr": b["gp_nr"],
                "PLZ": b["plz"],
                "Ort": "Synthstadt",
                "Kanton": "AG",
                "WärmePumpe": "x" if has_hp else "-",
                "PV": "x" if has_pv else "-",
                "PV-Leistung in kWp": "6.5" if has_pv else "",
                "Batterie/Speicher": "x" if has_batt else "-",
                "Ladestation für Elektrofahrzeuge": "x" if has_ev else "-",
                "Wärmepumpenboiler": "",
                "Datum Unterschrift": "01.01.2022",
                "geplanter Baustart": "",
                "Übergabe": "",
                "InBetrieb-Datum": "15.03.2022",
            }
        )
        if rng.random() < 0.15:
            # Duplicate GP-Nr row, same info — the brief says this happens
            # for real (1192 rows / 878 unique GP-Nr).
            rows.append(dict(rows[-1]))

    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def make_mapping(buildings, mp_mapping_path: Path, zaehler_gp_path: Path, rng: random.Random) -> None:
    with open(mp_mapping_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["MP ID", "Zählpunktbezeichnung"])
        for b in buildings:
            for mp_id in b["mp_ids"]:
                writer.writerow([mp_id, f"ZP-{mp_id}"])
        # A couple of MP IDs with no Zählpunktbezeichnung match at all further
        # down the chain (unmapped audit case).
        writer.writerow(["MP-UNMAPPED-1", "ZP-UNMAPPED-1"])
        writer.writerow(["MP-UNMAPPED-2", "ZP-UNMAPPED-2"])

    with open(zaehler_gp_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["Zählpunktbezeichnung", "GPartner", "Anlage"])
        for b in buildings:
            for mp_id in b["mp_ids"]:
                writer.writerow([f"ZP-{mp_id}", b["gp_nr"], "A1"])
        # ZP-UNMAPPED-1/2 intentionally absent here too -> stays unmapped.


def generate_building_series(b, start, days, rng, weather_by_plz):
    """Yield (Datum, {label: value}) rows for one building's MP power series."""
    plz = b["plz"]
    profile = b["profile"]
    base_night = rng.uniform(0.2, 0.5)
    base_day = base_night + rng.uniform(0.3, 0.9)

    for d in daterange(start, days):
        if rng.random() < 0.02:
            continue  # simulate a fully missing day (meter offline)
        day_weather = weather_by_plz[(plz, d)]
        ev_session_today = ("ev" in profile) and rng.random() < 0.35
        ev_start_q = rng.choice([18 * 4, 19 * 4, 20 * 4, 22 * 4, 23 * 4]) if ev_session_today else None
        ev_len_q = rng.choice([6, 8, 12]) if ev_session_today else 0
        ev_power = rng.choice([3.7, 7.0, 11.0]) if ev_session_today else 0.0

        values = {}
        for qi, label in enumerate(QUARTER_LABELS):
            hour = qi // 4
            temp = day_weather[hour]["temperature_2m"]
            radiation = day_weather[hour]["shortwave_radiation"]

            load = base_night if (hour >= 22 or hour < 6) else base_day
            load += 0.6 * math.exp(-((hour - 7.5) ** 2) / 3) + 0.8 * math.exp(-((hour - 19) ** 2) / 4)
            load += rng.gauss(0, 0.05)

            if profile == "heatpump":
                load += max(0.0, (15 - temp)) * 0.25

            if "pv" in profile:
                pv_kwp = 6.5
                pv_gen = pv_kwp * (radiation / 1000.0)
                net = load - pv_gen
                if "battery" in profile and pv_gen > load and rng.random() < 0.8:
                    net = rng.uniform(-0.15, 0.15)  # battery absorbs the surplus
                load = net

            if "battery" in profile and 16 <= hour < 22 and rng.random() < 0.5:
                load = rng.uniform(-0.15, 0.15)  # evening discharge flattens grid draw

            if ev_session_today and ev_start_q <= qi < ev_start_q + ev_len_q:
                load += ev_power

            values[label] = round(load, 3)

        yield d, values


def generate(
    out: Path,
    n_buildings: int = 100,
    days: int = 60,
    start: date = date(2024, 6, 1),
    seed: int = 42,
    quiet: bool = False,
) -> list[dict]:
    """Write the full synthetic fixture under ``out`` and return the building list

    (also saved as ``out/truth.json``) so a test can check the pipeline output
    against what was injected.
    """
    log = (lambda *a: None) if quiet else print
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)

    buildings = []
    mp_counter = 1
    for i in range(n_buildings):
        gp_nr = f"GP{i:06d}"
        plz = rng.choice(PLZ_POOL)
        profile = DEVICE_PROFILES[i % len(DEVICE_PROFILES)]
        n_mp = 2 if rng.random() < 0.08 else 1
        mp_ids = []
        for _ in range(n_mp):
            mp_ids.append(f"MP{mp_counter:07d}")
            mp_counter += 1
        buildings.append(
            {
                "gp_nr": gp_nr,
                "plz": plz,
                "profile": profile,
                "mp_ids": mp_ids,
                "labeled": rng.random() < 0.5,  # rest are "unlabeled cohort" buildings
            }
        )

    log(f"Generating weather for {len(PLZ_POOL)} PLZ, {days} days...")
    weather_by_plz = build_weather_lookup(PLZ_POOL, start, days, seed)
    make_weather(PLZ_POOL, start, days, weather_by_plz, out / "weather")

    log("Generating mapping tables...")
    make_mapping(buildings, out / "mpid_zähler_mapping.csv", out / "Zähler-GP.csv", rng)

    log("Generating GIGI labels...")
    make_labels(buildings, out / "HackDays2026 - GIGI.csv", rng)

    log(f"Generating consumption for {len(buildings)} buildings x {days} days...")
    consumption_dir = out / "2024"
    consumption_dir.mkdir(parents=True, exist_ok=True)
    out_path = consumption_dir / "LG_AIM2Hackerdays_kWh_synth.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["MP ID", "OBIS-Code", "Datum", "PLZ", *CSV_COLUMN_ORDER])
        for b in buildings:
            for mp_id in b["mp_ids"]:
                for d, values in generate_building_series(b, start, days, rng, weather_by_plz):
                    row = [mp_id, "1-1:1.29.0*255", d.strftime("%d.%m.%Y"), b["plz"]]
                    row += [values[label] for label in CSV_COLUMN_ORDER]
                    writer.writerow(row)
        # A duplicate-OBIS row for one MP+day, to exercise duplicate collapsing.
        first_mp = buildings[0]["mp_ids"][0]
        first_day = start
        dup_row = [first_mp, "1-1:2.29.0*255", first_day.strftime("%d.%m.%Y"), buildings[0]["plz"]]
        dup_row += [0.0 for _ in CSV_COLUMN_ORDER]
        writer.writerow(dup_row)
        # Rows for the two unmapped MP IDs (present in consumption, absent
        # from the mapping chain) so the unmapped-MP audit has something to
        # report.
        for mp_id in ("MP-UNMAPPED-1", "MP-UNMAPPED-2"):
            for d, values in generate_building_series(
                {"plz": PLZ_POOL[0], "profile": "baseline", "mp_ids": []}, start, min(5, days), rng, weather_by_plz
            ):
                row = [mp_id, "1-1:1.29.0*255", d.strftime("%d.%m.%Y"), PLZ_POOL[0]]
                row += [values[label] for label in CSV_COLUMN_ORDER]
                writer.writerow(row)

    truth_path = out / "truth.json"
    import json

    truth_path.write_text(
        json.dumps([{"gp_nr": b["gp_nr"], "profile": b["profile"], "labeled": b["labeled"]} for b in buildings], indent=2),
        encoding="utf-8",
    )
    log(f"Done. Ground truth for validation written to {truth_path}")
    return buildings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--buildings", type=int, default=100)
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--start-date", type=str, default="2024-06-01")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    generate(
        args.out,
        n_buildings=args.buildings,
        days=args.days,
        start=date.fromisoformat(args.start_date),
        seed=args.seed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
