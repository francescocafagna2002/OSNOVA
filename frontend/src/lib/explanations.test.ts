import { describe, expect, it } from "vitest";

import { describeSignal, summarizePrediction } from "@/lib/explanations";

describe("describeSignal", () => {
  it("translates known model features into everyday words", () => {
    expect(describeSignal("Repeated 7 kW events")).toMatch(/car charging/);
  });

  it("falls back to the raw feature name", () => {
    expect(describeSignal("Some new backend feature")).toBe("Some new backend feature");
  });
});

describe("summarizePrediction", () => {
  it("picks the sentence for the prediction label", () => {
    expect(summarizePrediction("pv", 92)).toMatch(/solar panels/);
    expect(summarizePrediction("pv", 92)).not.toMatch(/unlikely/);
    expect(summarizePrediction("heatPump", 31)).toMatch(/unlikely/);
    expect(summarizePrediction("ev", 76)).toMatch(/not regularly enough/);
  });
});
