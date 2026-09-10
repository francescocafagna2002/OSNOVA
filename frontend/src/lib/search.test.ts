import { describe, expect, it } from "vitest";

import { filterBuildings, normalizeText } from "@/lib/search";
import type { Building } from "@/lib/types";

const stub = (id: string, postcode: string, city: string) => ({ id, postcode, city }) as Building;

const buildings = [
  stub("AG-004711", "5000", "Aarau"),
  stub("AG-000002", "5400", "Baden"),
  stub("AG-000003", "8967", "Widen"),
  stub("AG-000004", "5610", "Wohlen AG"),
];

describe("normalizeText", () => {
  it("lowercases, strips diacritics and collapses whitespace", () => {
    expect(normalizeText("  Zürcher   Straße ")).toBe("zurcher straße");
    expect(normalizeText("Möhlin")).toBe("mohlin");
  });
});

describe("filterBuildings", () => {
  it("returns the same array for an empty query", () => {
    expect(filterBuildings(buildings, "   ")).toBe(buildings);
  });

  it("matches by id, postcode or town, case-insensitively", () => {
    expect(filterBuildings(buildings, "ag-004711").map((b) => b.id)).toEqual(["AG-004711"]);
    expect(filterBuildings(buildings, "54").map((b) => b.id)).toEqual(["AG-000002"]);
    expect(filterBuildings(buildings, "WOHLEN").map((b) => b.id)).toEqual(["AG-000004"]);
  });

  it("requires every token to match", () => {
    expect(filterBuildings(buildings, "5000 baden")).toEqual([]);
    expect(filterBuildings(buildings, "5000 aarau").map((b) => b.id)).toEqual(["AG-004711"]);
  });
});
