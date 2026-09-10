import { describe, expect, it } from "vitest";

import {
  buildChartOption,
  DAY_MINUTES,
  eventsToBands,
  formatClock,
  formatHourTick,
  hexToRgba,
  minutesFromStart,
  TICK_MINUTES,
} from "@/lib/chart-option";
import { makeBuilding } from "@/test/fixtures";

const startMs = Date.parse("2026-09-09T00:00:00+02:00");

describe("time helpers", () => {
  it("converts timestamps to minutes from the series start", () => {
    expect(minutesFromStart("2026-09-09T22:15:00+02:00", startMs)).toBe(1335);
    expect(minutesFromStart("2026-09-10T01:30:00+02:00", startMs)).toBe(1530);
  });

  it("formats ticks as two-digit hours and clock times as HH:MM", () => {
    expect(formatHourTick(0)).toBe("00");
    expect(formatHourTick(240)).toBe("04");
    expect(formatHourTick(1440)).toBe("24");
    expect(formatClock(1335)).toBe("22:15");
    expect(formatClock(5)).toBe("00:05");
  });

  it("converts hex to rgba", () => {
    expect(hexToRgba("#2563eb", 0.14)).toBe("rgba(37, 99, 235, 0.14)");
  });
});

describe("eventsToBands", () => {
  it("splits an event crossing midnight into a tail band and a head band", () => {
    const bands = eventsToBands(
      [{ type: "ev_charging", start: "2026-09-09T22:15:00+02:00", end: "2026-09-10T01:30:00+02:00" }],
      startMs,
    );
    expect(bands.map((b) => [b.startMin, b.endMin])).toEqual([
      [1335, 1440],
      [0, 90],
    ]);
    expect(bands.every((b) => b.label === "EV charging")).toBe(true);
  });

  it("clips bands to the day and drops events entirely outside it", () => {
    const bands = eventsToBands(
      [
        { type: "pv_generation", start: "2026-09-08T23:00:00+02:00", end: "2026-09-09T00:30:00+02:00" },
        { type: "high_consumption", start: "2026-09-11T10:00:00+02:00", end: "2026-09-11T12:00:00+02:00" },
      ],
      startMs,
    );
    expect(bands.map((b) => [b.type, b.startMin, b.endMin])).toEqual([
      ["pv_generation", 0, 30],
      ["pv_generation", 1380, 1440],
    ]);
  });
});

describe("buildChartOption", () => {
  const building = makeBuilding();
  const option = buildChartOption(building.electricity, building.events);

  it("uses a 0..1440 value axis with 4-hour ticks and no animation", () => {
    const xAxis = option.xAxis as { min: number; max: number; interval: number };
    expect(xAxis.min).toBe(0);
    expect(xAxis.max).toBe(DAY_MINUTES);
    expect(xAxis.interval).toBe(TICK_MINUTES);
    expect(option.animation).toBe(false);
  });

  it("plots [minute, kW] pairs and one markArea per band", () => {
    const [series] = option.series as Array<{ data: [number, number][]; markArea: { data: unknown[] } }>;
    expect(series.data).toEqual([
      [0, 0.4],
      [15, 0.5],
      [30, 7.2],
    ]);
    expect(series.markArea.data).toHaveLength(3); // EV tail + EV head + PV
  });

  it("handles an empty series", () => {
    const empty = buildChartOption([], []);
    const [series] = empty.series as Array<{ data: unknown[] }>;
    expect(series.data).toEqual([]);
  });
});
