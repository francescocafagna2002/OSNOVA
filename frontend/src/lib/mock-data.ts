import { getPlzArea } from "@/lib/plz";
import { createRng, type Rng } from "@/lib/random";
import {
  ASSET_KEYS,
  type AssetExplanation,
  type AssetKey,
  type AssetPrediction,
  type Building,
  type BuildingEvent,
  type BuildingExplanation,
  type ElectricityPoint,
} from "@/lib/types";

const MOCK_SEED = 42;
export const MOCK_BUILDING_COUNT = 120;
/** Local midnight in Europe/Zurich (CEST). Timestamps are emitted with this offset. */
export const MOCK_DAY_START = "2026-09-09T00:00:00+02:00";
export const DEMO_BUILDING_ID = "AG-004711";

const TZ_OFFSET_MINUTES = 120;
const STEP_MINUTES = 15;
const POINTS_PER_DAY = 96;
const DAY_MINUTES = 1440;
const EV_PLATEAU_KW = 7;
const DAY_START_MS = Date.parse(MOCK_DAY_START);

/** Aargau postal codes used for mock buildings; every code must exist in src/data/aargau-plz.json. */
export const MOCK_PLZ_POOL: readonly { plz: string; weight: number }[] = [
  { plz: "5000", weight: 8 },
  { plz: "5400", weight: 6 },
  { plz: "5200", weight: 4 },
  { plz: "5600", weight: 4 },
  { plz: "4800", weight: 4 },
  { plz: "4310", weight: 3 },
  { plz: "5610", weight: 3 },
  { plz: "4663", weight: 2 },
  { plz: "4313", weight: 2 },
  { plz: "5070", weight: 2 },
  { plz: "5630", weight: 2 },
  { plz: "5330", weight: 2 },
  { plz: "5734", weight: 2 },
  { plz: "5034", weight: 2 },
  { plz: "5033", weight: 2 },
  { plz: "8957", weight: 2 },
  { plz: "5430", weight: 3 },
  { plz: "4665", weight: 2 },
  { plz: "5507", weight: 1 },
  { plz: "5620", weight: 2 },
];

/** Minutes from day start; `end` may exceed DAY_MINUTES when an event crosses midnight. */
type Window = { start: number; end: number };
type EventWindows = { ev: Window[]; pv?: Window; high?: Window };

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** ISO 8601 with the fixed +02:00 offset, e.g. minute 1335 → "2026-09-09T22:15:00+02:00". */
function isoAtMinute(minute: number): string {
  const local = new Date(DAY_START_MS + (minute + TZ_OFFSET_MINUTES) * 60_000);
  return `${local.toISOString().slice(0, 19)}+02:00`;
}

function pickPlz(rng: Rng): string {
  const total = MOCK_PLZ_POOL.reduce((sum, entry) => sum + entry.weight, 0);
  let roll = rng.between(0, total);
  for (const entry of MOCK_PLZ_POOL) {
    roll -= entry.weight;
    if (roll <= 0) return entry.plz;
  }
  return MOCK_PLZ_POOL[MOCK_PLZ_POOL.length - 1].plz;
}

function pickPredictions(rng: Rng): AssetPrediction {
  const pv = rng.int(5, 98);
  const battery = pv >= 70 ? rng.int(30, 90) : rng.int(3, 45);
  const heatPump = rng.int(5, 95);
  const ev = rng.int(5, 95);
  return { pv, battery, heatPump, ev };
}

function pickWindows(rng: Rng, predictions: AssetPrediction): EventWindows {
  const windows: EventWindows = { ev: [] };
  if (predictions.ev >= 50) {
    const start = rng.int(84, 92) * STEP_MINUTES; // 21:00 – 23:00
    const duration = rng.int(8, 14) * STEP_MINUTES; // 2h – 3.5h, may cross midnight
    windows.ev.push({ start, end: start + duration });
  }
  if (predictions.pv >= 50) {
    windows.pv = { start: 600 + rng.int(-3, 3) * STEP_MINUTES, end: 990 + rng.int(-3, 3) * STEP_MINUTES };
  }
  if ((windows.ev.length === 0 && !windows.pv) || rng.chance(0.3)) {
    windows.high = { start: 1080, end: 1200 };
  }
  return windows;
}

function inWindow(minute: number, window: Window): boolean {
  if (minute >= window.start && minute < window.end) return true;
  // A window crossing midnight also covers the first minutes of this synthetic day.
  return window.end > DAY_MINUTES && minute < window.end - DAY_MINUTES;
}

function bell(x: number, center: number, width: number): number {
  return Math.exp(-((x - center) ** 2) / (2 * width * width));
}

function synthesizeElectricity(rng: Rng, predictions: AssetPrediction, windows: EventWindows): ElectricityPoint[] {
  const points: ElectricityPoint[] = [];
  for (let i = 0; i < POINTS_PER_DAY; i++) {
    const minute = i * STEP_MINUTES;
    const hour = minute / 60;
    let kw = 0.35 + rng.between(0, 0.15);
    kw += 0.8 * bell(hour, 7.5, 1);
    kw += 1.2 * bell(hour, 19, 1.5);
    if (predictions.heatPump >= 50) {
      const cycling = i % 4 < 2 ? 1.4 : 0.2;
      const daypart = hour < 9 || hour > 17 ? 1 : 0.5;
      kw += cycling * daypart;
    }
    if (predictions.pv >= 50 && windows.pv) {
      const peak = 2.5 + 3 * (predictions.pv / 100);
      const t = (minute - windows.pv.start) / (windows.pv.end - windows.pv.start);
      if (t > 0 && t < 1) kw -= peak * Math.sin(Math.PI * t);
    }
    if (predictions.battery >= 50) {
      kw -= 0.6 * bell(hour, 19, 1.5);
      kw += 0.4 * bell(hour, 13, 1.5);
    }
    if (windows.ev.some((window) => inWindow(minute, window))) {
      kw += EV_PLATEAU_KW + rng.between(-0.2, 0.2);
    }
    points.push({ timestamp: isoAtMinute(minute), powerKw: round2(kw) });
  }
  return points;
}

function windowsToEvents(windows: EventWindows, confidences: { ev: number; pv: number; high: number }): BuildingEvent[] {
  const events: BuildingEvent[] = windows.ev.map((window) => ({
    type: "ev_charging",
    start: isoAtMinute(window.start),
    end: isoAtMinute(window.end),
    confidence: confidences.ev,
  }));
  if (windows.pv) {
    events.push({ type: "pv_generation", start: isoAtMinute(windows.pv.start), end: isoAtMinute(windows.pv.end), confidence: confidences.pv });
  }
  if (windows.high) {
    events.push({ type: "high_consumption", start: isoAtMinute(windows.high.start), end: isoAtMinute(windows.high.end), confidence: confidences.high });
  }
  return events.slice(0, 3);
}

const REASONS: Record<AssetKey, { likely: string[]; unlikely: string[] }> = {
  pv: {
    likely: ["Recurring midday reduction in net consumption", "Reduction scales with expected sunshine hours", "Pattern repeats across consecutive days"],
    unlikely: ["No consistent midday reduction in net load", "Daytime consumption follows a typical household shape"],
  },
  battery: {
    likely: ["Evening peak is flatter than similar households", "Midday surplus is absorbed rather than exported", "Charge and discharge cycles follow the PV pattern"],
    unlikely: ["Evening peak shape matches households without storage", "Midday surplus is exported rather than stored"],
  },
  heatPump: {
    likely: ["Regular on/off cycling of a 1–2 kW load", "Higher baseline in morning and evening hours", "Consumption rises when outdoor temperature drops"],
    unlikely: ["No regular cycling load detected", "Baseline consumption is stable across the day"],
  },
  ev: {
    likely: ["Repeated high-power events", "Mostly during nighttime", "Similar duration across multiple days"],
    unlikely: ["No repeated high-power plateaus", "Nighttime consumption stays near baseline"],
  },
};

const SHAP_FEATURES: Record<AssetKey, [string, string, string, string]> = {
  pv: ["Midday net-load dip", "Clear-sky day correlation", "Seasonal amplitude", "Nighttime baseline"],
  battery: ["Evening peak flattening", "Midday absorption", "Cycle regularity", "Export events"],
  heatPump: ["Cycling frequency", "Temperature sensitivity", "Morning baseline", "Summer consumption"],
  ev: ["High nighttime power peak", "Repeated 7 kW events", "Event duration", "Daytime consumption pattern"],
};

const MODEL_META = {
  model: "Machine learning classification model",
  inputs: ["15-minute electricity measurements"],
  additionalData: ["Weather / temperature (if available)"],
  method: "SHAP",
  methodDescription: "SHAP shows which features contributed most to the prediction.",
} as const;

function generateAssetExplanation(rng: Rng, key: AssetKey, probability: number): AssetExplanation {
  const p = probability / 100;
  const likely = p >= 0.5;
  const strength = likely ? p : 1 - p;
  const shap = SHAP_FEATURES[key].map((feature, index) => {
    const magnitude = strength * (0.35 - index * 0.08) + rng.between(-0.03, 0.03);
    const supportsAsset = index < 3; // three features for, one against
    const sign = (supportsAsset ? 1 : -1) * (likely ? 1 : -1);
    return { feature, contribution: round2(sign * Math.abs(magnitude)) };
  });
  return { reasons: likely ? REASONS[key].likely : REASONS[key].unlikely, shap };
}

function generateExplanation(rng: Rng, predictions: AssetPrediction): BuildingExplanation {
  const assets = Object.fromEntries(
    ASSET_KEYS.map((key) => [key, generateAssetExplanation(rng, key, predictions[key])]),
  ) as Record<AssetKey, AssetExplanation>;
  return { ...MODEL_META, inputs: [...MODEL_META.inputs], additionalData: [...MODEL_META.additionalData], assets };
}

/** Hand-authored so the demo matches the task doc's SHAP example exactly. */
const DEMO_EXPLANATION: BuildingExplanation = {
  ...MODEL_META,
  inputs: [...MODEL_META.inputs],
  additionalData: [...MODEL_META.additionalData],
  assets: {
    pv: {
      reasons: REASONS.pv.likely,
      shap: [
        { feature: "Midday net-load dip", contribution: 0.38 },
        { feature: "Clear-sky day correlation", contribution: 0.22 },
        { feature: "Seasonal amplitude", contribution: 0.12 },
        { feature: "Nighttime baseline", contribution: -0.02 },
      ],
    },
    battery: {
      reasons: REASONS.battery.unlikely,
      shap: [
        { feature: "Evening peak flattening", contribution: 0.09 },
        { feature: "Midday absorption", contribution: 0.06 },
        { feature: "Cycle regularity", contribution: -0.05 },
        { feature: "Export events", contribution: -0.11 },
      ],
    },
    heatPump: {
      reasons: REASONS.heatPump.unlikely,
      shap: [
        { feature: "Cycling frequency", contribution: -0.21 },
        { feature: "Temperature sensitivity", contribution: -0.12 },
        { feature: "Morning baseline", contribution: 0.05 },
        { feature: "Summer consumption", contribution: -0.03 },
      ],
    },
    ev: {
      reasons: REASONS.ev.likely,
      shap: [
        { feature: "High nighttime power peak", contribution: 0.31 },
        { feature: "Repeated 7 kW events", contribution: 0.24 },
        { feature: "Event duration", contribution: 0.15 },
        { feature: "Daytime consumption pattern", contribution: -0.04 },
      ],
    },
  },
};

function buildDemoBuilding(rng: Rng): Building {
  const predictions: AssetPrediction = { pv: 92, battery: 48, heatPump: 31, ev: 76 };
  const windows: EventWindows = { ev: [{ start: 1335, end: DAY_MINUTES + 90 }], pv: { start: 600, end: 990 } };
  return {
    id: DEMO_BUILDING_ID,
    postcode: "5000",
    city: getPlzArea("5000")?.name ?? "Aarau",
    canton: "AG",
    predictions,
    electricity: synthesizeElectricity(rng, predictions, windows),
    events: windowsToEvents(windows, { ev: 0.9, pv: 0.85, high: 0.6 }),
    explanation: DEMO_EXPLANATION,
  };
}

/** Deterministic: same seed and count always yield the same buildings. Demo building first. */
export function generateMockBuildings(seed = MOCK_SEED, count = MOCK_BUILDING_COUNT): Building[] {
  const rng = createRng(seed);
  const buildings: Building[] = [buildDemoBuilding(rng)];
  const usedIds = new Set(buildings.map((b) => b.id));
  while (buildings.length < count) {
    const id = `AG-${String(rng.int(1, 999_999)).padStart(6, "0")}`;
    if (usedIds.has(id)) continue;
    usedIds.add(id);
    const postcode = pickPlz(rng);
    const predictions = pickPredictions(rng);
    const windows = pickWindows(rng, predictions);
    buildings.push({
      id,
      postcode,
      city: getPlzArea(postcode)?.name ?? postcode,
      canton: "AG",
      predictions,
      electricity: synthesizeElectricity(rng, predictions, windows),
      events: windowsToEvents(windows, {
        ev: round2(rng.between(0.7, 0.95)),
        pv: round2(rng.between(0.6, 0.9)),
        high: round2(rng.between(0.5, 0.8)),
      }),
      explanation: generateExplanation(rng, predictions),
    });
  }
  return buildings;
}
