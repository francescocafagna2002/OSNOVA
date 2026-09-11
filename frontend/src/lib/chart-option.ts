import type { EChartsOption } from "echarts";

import { EVENT_META } from "@/lib/events";
import { CHART } from "@/lib/theme";
import type { BuildingEvent, BuildingEventType, ElectricityPoint } from "@/lib/types";

export const DAY_MINUTES = 1440;
export const TICK_MINUTES = 240;
export const LINE_COLOR = CHART.line;
const GRID_COLOR = CHART.grid;
const AXIS_TEXT_COLOR = CHART.axis;
const AXIS_FONT_FAMILY = "Inter, Arial, sans-serif";
const AXIS_FONT_SIZE = 12;

/** Fill alpha per band type (R12); keeps the consumption line the primary element. */
const BAND_OPACITY: Record<BuildingEventType, number> = {
  pv_generation: 0.14,
  ev_charging: 0.12,
  heat_pump_heating: 0.12,
  battery_cycle: 0.12,
  high_consumption: 0.1,
};

/** Band label colour per type (R12); PV uses a darker warm tone than its fill. */
const BAND_LABEL_COLOR: Record<BuildingEventType, string> = {
  ev_charging: "#0065A8",
  pv_generation: "#B8791A",
  heat_pump_heating: "#B4451F",
  battery_cycle: "#2B7D44",
  high_consumption: "#65727D",
};

export function minutesFromStart(iso: string, startMs: number): number {
  return (Date.parse(iso) - startMs) / 60_000;
}

/** 0 → "00", 240 → "04", 1440 → "24". */
export function formatHourTick(minute: number): string {
  return String(Math.round(minute / 60)).padStart(2, "0");
}

/** 1335 → "22:15". */
export function formatClock(minute: number): string {
  const whole = Math.round(minute);
  const hh = String(Math.floor(whole / 60)).padStart(2, "0");
  const mm = String(whole % 60).padStart(2, "0");
  return `${hh}:${mm}`;
}

export function hexToRgba(hex: string, alpha: number): string {
  const value = Number.parseInt(hex.slice(1), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

type EventBand = {
  type: BuildingEventType;
  label: string;
  color: string;
  startMin: number;
  endMin: number;
};

/**
 * Converts events to minute bands inside [0, DAY_MINUTES]. A band that runs past
 * the day end keeps its in-day part and folds the overflow to the start of the
 * day (the previous night's tail); a band that starts before the day folds
 * symmetrically. An event can only fold onto one side at a time: if it starts
 * before the day AND still runs past the day end, it already covers the whole
 * day, so it collapses to a single [0, DAY_MINUTES] band instead of folding
 * onto both ends (which would otherwise overlap). Empty bands are dropped.
 */
export function eventsToBands(events: BuildingEvent[], startMs: number): EventBand[] {
  const bands: EventBand[] = [];
  for (const event of events) {
    const meta = EVENT_META[event.type];
    const start = minutesFromStart(event.start, startMs);
    const end = minutesFromStart(event.end, startMs);
    if (end <= 0 || start >= DAY_MINUTES) continue; // entirely outside the day

    const segments: [number, number][] = [];
    if (start <= 0 && end >= DAY_MINUTES) {
      segments.push([0, DAY_MINUTES]); // covers the whole day; nothing left to fold
    } else {
      segments.push([Math.max(0, start), Math.min(DAY_MINUTES, end)]);
      if (end > DAY_MINUTES) segments.push([0, end - DAY_MINUTES]);
      if (start < 0) segments.push([start + DAY_MINUTES, DAY_MINUTES]);
    }

    for (const [segmentStart, segmentEnd] of segments) {
      if (segmentEnd > segmentStart) {
        bands.push({ type: event.type, label: meta.label, color: meta.color, startMin: segmentStart, endMin: segmentEnd });
      }
    }
  }
  return bands;
}

type AxisTooltipParam = { value: [number, number] };

function tooltipFormatter(params: unknown): string {
  const list = (Array.isArray(params) ? params : [params]) as AxisTooltipParam[];
  const first = list[0];
  if (!first) return "";
  const [minute, kw] = first.value;
  return `${formatClock(minute)} · ${kw.toFixed(2)} kW`;
}

export function buildChartOption(electricity: ElectricityPoint[], events: BuildingEvent[]): EChartsOption {
  const startMs = electricity.length > 0 ? Date.parse(electricity[0].timestamp) : 0;
  const data = electricity.map((point): [number, number] => [minutesFromStart(point.timestamp, startMs), point.powerKw]);
  const bands = electricity.length > 0 ? eventsToBands(events, startMs) : [];

  return {
    animation: false,
    grid: { left: 48, right: 16, top: 24, bottom: 32 },
    tooltip: {
      trigger: "axis",
      formatter: tooltipFormatter,
      backgroundColor: "#fff",
      borderColor: "#D9E0E6",
      borderWidth: 1,
      textStyle: { color: "#182638" },
    },
    xAxis: {
      type: "value",
      min: 0,
      max: DAY_MINUTES,
      interval: TICK_MINUTES,
      axisLabel: {
        formatter: (value: number) => formatHourTick(value),
        color: AXIS_TEXT_COLOR,
        fontSize: AXIS_FONT_SIZE,
        fontFamily: AXIS_FONT_FAMILY,
      },
      axisLine: { lineStyle: { color: GRID_COLOR } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: "value",
      name: "kW",
      nameTextStyle: { color: AXIS_TEXT_COLOR, align: "right", fontSize: AXIS_FONT_SIZE, fontFamily: AXIS_FONT_FAMILY },
      axisLabel: { color: AXIS_TEXT_COLOR, fontSize: AXIS_FONT_SIZE, fontFamily: AXIS_FONT_FAMILY },
      splitLine: { lineStyle: { color: GRID_COLOR } },
    },
    series: [
      {
        name: "Net power",
        type: "line",
        data,
        showSymbol: false,
        smooth: false,
        lineStyle: { width: 2.5, color: LINE_COLOR },
        itemStyle: { color: LINE_COLOR },
        markArea: {
          silent: true,
          data: bands.map((band) => [
            {
              name: band.label,
              xAxis: band.startMin,
              itemStyle: { color: hexToRgba(band.color, BAND_OPACITY[band.type]) },
              label: { show: true, position: "insideTop", color: BAND_LABEL_COLOR[band.type], fontSize: 11, fontWeight: 500 },
            },
            { xAxis: band.endMin },
          ]),
        },
      },
    ],
  };
}
