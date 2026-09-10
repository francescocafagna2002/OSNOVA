"use client";

import ReactECharts from "echarts-for-react";
import { useMemo } from "react";

import { ChartLegend } from "@/components/chart/chart-legend";
import { buildChartOption } from "@/lib/chart-option";
import type { BuildingEvent, ElectricityPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

const CHART_HEIGHT = 260;

type ElectricityChartProps = {
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  className?: string;
};

/**
 * 24h net-power line with event bands (task doc §10–§11). Only ever mounted
 * inside the client-side detail sheet, so no dynamic import is needed.
 */
export function ElectricityChart({ electricity, events, className }: ElectricityChartProps) {
  const option = useMemo(() => buildChartOption(electricity, events), [electricity, events]);
  return (
    <div
      data-testid="electricity-chart"
      data-points={electricity.length}
      data-events={events.length}
      className={cn("space-y-2 rounded-lg border border-border bg-white p-4", className)}
    >
      <ReactECharts option={option} notMerge style={{ height: CHART_HEIGHT, width: "100%" }} opts={{ renderer: "svg" }} />
      <ChartLegend events={events} />
    </div>
  );
}
