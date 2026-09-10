import { BatteryCharging, Car, Flame, Sun, type LucideIcon } from "lucide-react";

import type { AssetKey, AssetPrediction } from "@/lib/types";

/** Tune during the hackathon; every label in the UI derives from these. Inclusive lower bounds. */
export const PREDICTION_THRESHOLDS = { likely: 80, possible: 50 } as const;

export type PredictionLabel = "Likely" | "Possible" | "Unlikely";

function clampProbability(probability: number): number {
  if (Number.isNaN(probability)) return 0;
  return Math.min(100, Math.max(0, probability));
}

export function getPredictionLabel(probability: number): PredictionLabel {
  const p = clampProbability(probability);
  if (p >= PREDICTION_THRESHOLDS.likely) return "Likely";
  if (p >= PREDICTION_THRESHOLDS.possible) return "Possible";
  return "Unlikely";
}

export function formatProbability(probability: number): string {
  return `${Math.round(clampProbability(probability))}%`;
}

export type AssetMeta = {
  key: AssetKey;
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  color: string;
};

/** Fixed display order: PV, Battery, Heat pump, EV. */
export const ASSETS: readonly AssetMeta[] = [
  { key: "pv", label: "PV / Solar", shortLabel: "PV", icon: Sun, color: "#d97706" },
  { key: "battery", label: "Battery", shortLabel: "Battery", icon: BatteryCharging, color: "#16a34a" },
  { key: "heatPump", label: "Heat pump", shortLabel: "Heat pump", icon: Flame, color: "#ea580c" },
  { key: "ev", label: "Electric vehicle", shortLabel: "EV", icon: Car, color: "#2563eb" },
];

export const ASSET_BY_KEY = Object.fromEntries(ASSETS.map((asset) => [asset.key, asset])) as Record<
  AssetKey,
  AssetMeta
>;

/** Asset keys labelled "Likely", highest probability first, at most `max`. */
export function getMarkerAssets(predictions: AssetPrediction, max = 2): AssetKey[] {
  return ASSETS.map((asset) => asset.key)
    .filter((key) => getPredictionLabel(predictions[key]) === "Likely")
    .sort((a, b) => predictions[b] - predictions[a])
    .slice(0, max);
}

/** "EV — 76% possible". Phrases the prediction as a probability, never as a fact. */
export function describePrediction(assetKey: AssetKey, probability: number): string {
  const label = getPredictionLabel(probability).toLowerCase();
  return `${ASSET_BY_KEY[assetKey].shortLabel} — ${formatProbability(probability)} ${label}`;
}
