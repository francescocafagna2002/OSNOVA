import { describe, expect, it } from "vitest";

import {
  AARGAU_BBOX,
  buildPlzGeoJson,
  countBuildingsByPlz,
  formatPlz,
  getPlzArea,
  PLZ_AREAS,
  PLZ_BY_CODE,
} from "@/lib/plz";
import type { Building } from "@/lib/types";

describe("PLZ areas", () => {
  it("loads every Aargau PLZ polygon with a name and a bbox", () => {
    expect(PLZ_AREAS.length).toBe(239);
    const aarau = getPlzArea("5000");
    expect(aarau?.name).toBe("Aarau");
    expect(aarau?.gemeinde).toBe("Aarau");
    expect(aarau?.bbox[0]).toBeLessThan(aarau!.bbox[2]);
    expect(aarau?.bbox[1]).toBeLessThan(aarau!.bbox[3]);
    expect(PLZ_BY_CODE["5400"].name).toBe("Baden");
  });

  it("returns undefined for unknown codes", () => {
    expect(getPlzArea("9999")).toBeUndefined();
  });

  it("exposes a canton-wide bbox in lng/lat order", () => {
    const [west, south, east, north] = AARGAU_BBOX;
    expect(west).toBeGreaterThan(7.5);
    expect(east).toBeLessThan(8.6);
    expect(south).toBeGreaterThan(47.0);
    expect(north).toBeLessThan(47.7);
  });

  it("formats a code with its town name and falls back to the code", () => {
    expect(formatPlz("5000")).toBe("5000 Aarau");
    expect(formatPlz("9999")).toBe("9999");
  });
});

describe("countBuildingsByPlz / buildPlzGeoJson", () => {
  const stub = (id: string, postcode: string) => ({ id, postcode }) as Building;

  it("counts buildings per postcode", () => {
    expect(countBuildingsByPlz([stub("a", "5000"), stub("b", "5000"), stub("c", "5400")])).toEqual({
      "5000": 2,
      "5400": 1,
    });
  });

  it("adds a numeric count to every feature, zero when absent", () => {
    const geo = buildPlzGeoJson({ "5000": 2 });
    const aarau = geo.features.find((f) => f.properties.plz === "5000");
    const baden = geo.features.find((f) => f.properties.plz === "5400");
    expect(aarau?.properties.count).toBe(2);
    expect(baden?.properties.count).toBe(0);
    expect(geo.features.length).toBe(239);
  });
});
