import { describe, expect, it } from "vitest";

import {
  DEMO_BUILDING_ID,
  generateMockBuildings,
  MOCK_BUILDING_COUNT,
  MOCK_PLZ_POOL,
} from "@/lib/mock-data";
import { getPlzArea } from "@/lib/plz";
import { ASSET_KEYS } from "@/lib/types";

describe("generateMockBuildings", () => {
  const buildings = generateMockBuildings();

  it("is deterministic and has the configured size with unique ids", () => {
    expect(buildings).toEqual(generateMockBuildings());
    expect(buildings.length).toBe(MOCK_BUILDING_COUNT);
    expect(new Set(buildings.map((b) => b.id)).size).toBe(MOCK_BUILDING_COUNT);
  });

  it("puts the hand-authored demo building first", () => {
    const demo = buildings[0];
    expect(demo.id).toBe(DEMO_BUILDING_ID);
    expect(demo.postcode).toBe("5000");
    expect(demo.city).toBe("Aarau");
    expect(demo.canton).toBe("AG");
    expect(demo.predictions).toEqual({ pv: 92, battery: 48, heatPump: 31, ev: 76 });
    expect(demo.events).toEqual([
      { type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00", confidence: 0.9 },
      { type: "pv_generation", start: "2026-09-09T10:00:00+02:00", end: "2026-09-09T16:30:00+02:00", confidence: 0.85 },
    ]);
    expect(demo.explanation.assets.ev.shap.map((s) => s.contribution)).toEqual([0.31, 0.24, 0.15, -0.04]);
  });

  it("gives the demo building an EV plateau at night and a PV dip at midday", () => {
    const demo = buildings[0];
    const at = (hhmm: string) => demo.electricity.find((p) => p.timestamp.includes(`T${hhmm}:00+02:00`))!.powerKw;
    expect(at("22:30")).toBeGreaterThan(6.5);
    expect(at("00:45")).toBeGreaterThan(6.5);
    expect(at("13:00")).toBeLessThan(0);
    expect(at("04:00")).toBeLessThan(2);
  });

  it("uses only Aargau PLZs that exist in the polygon data", () => {
    for (const { plz } of MOCK_PLZ_POOL) expect(getPlzArea(plz), plz).toBeDefined();
    for (const b of buildings) {
      expect(getPlzArea(b.postcode), b.id).toBeDefined();
      expect(b.city).toBe(getPlzArea(b.postcode)!.name);
    }
  });

  it("gives every building a full day, 1–3 events and probabilities in range", () => {
    for (const b of buildings) {
      expect(b.electricity.length).toBe(96);
      expect(b.electricity[0].timestamp).toBe("2026-09-09T00:00:00+02:00");
      expect(b.events.length).toBeGreaterThanOrEqual(1);
      expect(b.events.length).toBeLessThanOrEqual(3);
      for (const e of b.events) expect(Date.parse(e.end)).toBeGreaterThan(Date.parse(e.start));
      for (const key of ASSET_KEYS) {
        expect(b.predictions[key]).toBeGreaterThanOrEqual(0);
        expect(b.predictions[key]).toBeLessThanOrEqual(100);
        expect(b.explanation.assets[key].reasons.length).toBeGreaterThan(0);
        expect(b.explanation.assets[key].shap.length).toBe(4);
      }
    }
  });
});
