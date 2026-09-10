import { describe, expect, it } from "vitest";

import {
  ASSETS,
  describePrediction,
  formatContribution,
  formatProbability,
  getPredictionLabel,
} from "@/lib/predictions";

describe("getPredictionLabel", () => {
  it.each([
    [100, "Likely"],
    [80, "Likely"],
    [79.9, "Possible"],
    [50, "Possible"],
    [49, "Unlikely"],
    [0, "Unlikely"],
  ])("maps %s to %s", (probability, label) => {
    expect(getPredictionLabel(probability)).toBe(label);
  });

  it("clamps out-of-range and NaN input", () => {
    expect(getPredictionLabel(150)).toBe("Likely");
    expect(getPredictionLabel(-5)).toBe("Unlikely");
    expect(getPredictionLabel(Number.NaN)).toBe("Unlikely");
  });
});

describe("formatProbability", () => {
  it("rounds and appends a percent sign", () => {
    expect(formatProbability(76.4)).toBe("76%");
    expect(formatProbability(120)).toBe("100%");
  });
});

describe("ASSETS", () => {
  it("keeps the fixed order PV, Battery, Heat pump, EV", () => {
    expect(ASSETS.map((a) => a.key)).toEqual(["pv", "battery", "heatPump", "ev"]);
  });
});

describe("describePrediction", () => {
  it("phrases predictions as probabilities, never as facts", () => {
    const text = describePrediction("ev", 76);
    expect(text).toBe("EV — 76% possible");
    expect(text.toLowerCase()).not.toContain("has");
  });
});

describe("formatContribution", () => {
  it("prints a sign and two decimals", () => {
    expect(formatContribution(0.31)).toBe("+0.31");
    expect(formatContribution(-0.04)).toBe("−0.04");
    expect(formatContribution(0)).toBe("+0.00");
  });
});
