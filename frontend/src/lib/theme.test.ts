import { describe, expect, it } from "vitest";

import { BRAND, CHART, MAP, NEUTRAL } from "@/lib/theme";

describe("BRAND", () => {
  it("exposes the AEW brand palette", () => {
    expect(BRAND).toEqual({
      blue: "#0065A8",
      navy: "#003B5C",
      blueHover: "#00558C",
      blueLight: "#EAF4FA",
    });
  });
});

describe("NEUTRAL", () => {
  it("exposes the neutral surface and text palette", () => {
    expect(NEUTRAL).toEqual({
      pageBg: "#F5F6F4",
      surfaceSoft: "#F7F9FB",
      borderLight: "#D9E0E6",
      borderMedium: "#C7D0D8",
      textSecondary: "#65727D",
      textPrimary: "#182638",
      textDark: "#102033",
    });
  });
});

describe("MAP", () => {
  it("exposes the basemap and PLZ layer palette", () => {
    expect(MAP).toEqual({
      background: "#F5F6F4",
      land: "#F7F8F6",
      roadMajor: "#FFFFFF",
      roadMinor: "#E3E5E4",
      water: "#DDE9ED",
      label: "#1F2933",
      plzFill: "#D8E7F5",
      plzBorder: "#7FA4C8",
      plzHover: "#D9E8F6",
      plzEmptyFill: "#CDD2D7",
      plzEmptyBorder: "#AEB5BC",
    });
  });
});

describe("CHART", () => {
  it("exposes the chart line, grid and axis colours", () => {
    expect(CHART).toEqual({
      line: "#18385A",
      grid: "#E1E6EA",
      axis: "#65727D",
    });
  });
});
