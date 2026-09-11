export const ASSET_KEYS = ["pv", "battery", "heatPump", "ev"] as const;
export type AssetKey = (typeof ASSET_KEYS)[number];

/** Probability per asset, 0–100. */
export type AssetPrediction = Record<AssetKey, number>;

export type ElectricityPoint = {
  timestamp: string; // ISO 8601 with offset
  powerKw: number; // net power; negative = export to grid
};

export const EVENT_TYPES = [
  "ev_charging",
  "pv_generation",
  "heat_pump_heating",
  "battery_cycle",
  "high_consumption",
] as const;
export type BuildingEventType = (typeof EVENT_TYPES)[number];

export type BuildingEvent = {
  type: BuildingEventType;
  start: string; // ISO 8601
  end: string; // ISO 8601, may be on the next day
  confidence?: number; // 0–1
};

export type ShapFeature = { feature: string; contribution: number }; // signed, roughly −1..1

export type AssetExplanation = {
  reasons: string[]; // plain-language evidence bullets for the "Why?" popover
  shap: ShapFeature[]; // signed contributions for the technical section
};

export type BuildingExplanation = {
  model: string;
  inputs: string[];
  additionalData: string[];
  method: string; // "SHAP"
  methodDescription: string; // one line
  assets: Record<AssetKey, AssetExplanation>;
};

export type Building = {
  id: string; // anonymised customer / meter id, e.g. "AG-004711"
  postcode: string; // PLZ, e.g. "5000"
  city: string; // town name from the data, e.g. "Aarau"
  canton: string; // "AG"
  predictions: AssetPrediction;
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  explanation: BuildingExplanation;
};
