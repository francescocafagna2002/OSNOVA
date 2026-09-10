import type { AssetExplanation, Building } from "@/lib/types";

const explanation = (reason: string, feature: string): AssetExplanation => ({
  reasons: [reason],
  shap: [
    { feature, contribution: 0.3 },
    { feature: "Secondary feature", contribution: 0.1 },
    { feature: "Tertiary feature", contribution: 0.05 },
    { feature: "Counter feature", contribution: -0.04 },
  ],
});

/** A realistic building for component tests; override any field. */
export function makeBuilding(overrides: Partial<Building> = {}): Building {
  return {
    id: "AG-000001",
    postcode: "5000",
    city: "Aarau",
    canton: "AG",
    predictions: { pv: 92, battery: 48, heatPump: 31, ev: 76 },
    electricity: [
      { timestamp: "2026-09-09T00:00:00+02:00", powerKw: 0.4 },
      { timestamp: "2026-09-09T00:15:00+02:00", powerKw: 0.5 },
      { timestamp: "2026-09-09T00:30:00+02:00", powerKw: 7.2 },
    ],
    events: [
      { type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00", confidence: 0.9 },
      { type: "pv_generation", start: "2026-09-09T10:00:00+02:00", end: "2026-09-09T16:30:00+02:00", confidence: 0.85 },
    ],
    explanation: {
      model: "Test model",
      inputs: ["15-minute electricity measurements"],
      additionalData: ["Weather / temperature (if available)"],
      method: "SHAP",
      methodDescription: "SHAP shows which features contributed most to the prediction.",
      assets: {
        pv: explanation("Recurring midday reduction in net consumption", "Midday net-load dip"),
        battery: explanation("Midday surplus is exported rather than stored", "Evening peak flattening"),
        heatPump: explanation("No regular cycling load detected", "Cycling frequency"),
        ev: explanation("Repeated high-power events", "High nighttime power peak"),
      },
    },
    ...overrides,
  };
}
