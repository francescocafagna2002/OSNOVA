import { describe, expect, it } from "vitest";

import {
  buildChartOption,
  DAY_MINUTES,
  eventsToBands,
  formatClock,
  formatHourTick,
  hexToRgba,
  LINE_COLOR,
  minutesFromStart,
  TICK_MINUTES,
} from "@/lib/chart-option";
import { ASSET_BY_KEY } from "@/lib/predictions";
import { CHART } from "@/lib/theme";
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

  it("draws the backend's heat-pump and battery events as bands with the asset colours", () => {
    const bands = eventsToBands(
      [
        { type: "heat_pump_heating", start: "2026-09-09T05:00:00+02:00", end: "2026-09-09T08:00:00+02:00" },
        { type: "battery_cycle", start: "2026-09-09T18:00:00+02:00", end: "2026-09-09T21:00:00+02:00" },
      ],
      startMs,
    );
    expect(bands.map((b) => [b.type, b.label, b.startMin, b.endMin])).toEqual([
      ["heat_pump_heating", "Heat pump heating", 300, 480],
      ["battery_cycle", "Battery charging / discharging", 1080, 1260],
    ]);
    expect(bands[0].color).toBe(ASSET_BY_KEY.heatPump.color);
    expect(bands[1].color).toBe(ASSET_BY_KEY.battery.color);
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

  it("collapses an event that straddles both day boundaries into a single full-day band", () => {
    const bands = eventsToBands(
      [{ type: "high_consumption", start: "2026-09-08T23:00:00+02:00", end: "2026-09-10T01:00:00+02:00" }],
      startMs,
    );
    expect(bands.map((b) => [b.startMin, b.endMin])).toEqual([[0, 1440]]);
  });

  it("collapses an event spanning exactly the whole day into a single full-day band", () => {
    const bands = eventsToBands(
      [{ type: "high_consumption", start: "2026-09-09T00:00:00+02:00", end: "2026-09-10T00:00:00+02:00" }],
      startMs,
    );
    expect(bands.map((b) => [b.startMin, b.endMin])).toEqual([[0, 1440]]);
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

  it("styles the line per R12: navy, 2.5px", () => {
    const [series] = option.series as Array<{ lineStyle: { width: number; color: string } }>;
    expect(LINE_COLOR).toBe(CHART.line);
    expect(series.lineStyle).toEqual({ width: 2.5, color: CHART.line });
  });

  it("styles axes with the secondary colour and 12px Inter labels", () => {
    const xAxis = option.xAxis as {
      axisLabel: { color: string; fontSize: number; fontFamily: string; formatter: unknown };
    };
    const yAxis = option.yAxis as {
      name: string;
      nameTextStyle: { color: string; fontSize: number; fontFamily: string };
      axisLabel: { color: string; fontSize: number; fontFamily: string };
    };
    expect(xAxis.axisLabel.color).toBe(CHART.axis);
    expect(xAxis.axisLabel.fontSize).toBe(12);
    expect(xAxis.axisLabel.fontFamily).toBe("Inter, Arial, sans-serif");
    expect(yAxis.name).toBe("kW");
    expect(yAxis.nameTextStyle.color).toBe(CHART.axis);
    expect(yAxis.axisLabel.color).toBe(CHART.axis);
  });

  it("keeps grid margins on the 8px scale", () => {
    const grid = option.grid as { left: number; right: number; top: number; bottom: number };
    for (const value of Object.values(grid)) {
      expect(value % 8).toBe(0);
    }
  });

  it("styles the tooltip white with a light border and dark text", () => {
    const tooltip = option.tooltip as { backgroundColor: string; borderColor: string; textStyle: { color: string } };
    expect(tooltip.backgroundColor).toBe("#fff");
    expect(tooltip.borderColor).toBe("#D9E0E6");
    expect(tooltip.textStyle.color).toBe("#182638");
  });

  it("fills each band type with its own opacity and label colour (R12)", () => {
    const [series] = option.series as Array<{
      markArea: { data: [{ itemStyle: { color: string }; label: { color: string } }, unknown][] };
    }>;
    const [evTail, , pv] = series.markArea.data;
    expect(evTail[0].itemStyle.color).toBe(hexToRgba("#0065A8", 0.12)); // EV band colour
    expect(evTail[0].label.color).toBe("#0065A8");
    expect(pv[0].itemStyle.color).toBe(hexToRgba("#EFA33A", 0.14));
    expect(pv[0].label.color).toBe("#B8791A");
  });
});
