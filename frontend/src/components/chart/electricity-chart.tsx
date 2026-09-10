"use client";

import type { BuildingEvent, ElectricityPoint } from "@/lib/types";

export type ElectricityChartProps = {
  electricity: ElectricityPoint[];
  events: BuildingEvent[];
  className?: string;
};

/**
 * Placeholder that fixes the chart's public interface so the detail panel can be
 * built in parallel. The chart task replaces the body, not the props.
 */
export function ElectricityChart({ electricity, events, className }: ElectricityChartProps) {
  return (
    <div
      data-testid="electricity-chart"
      data-points={electricity.length}
      data-events={events.length}
      className={className}
      style={{ height: 260 }}
    />
  );
}
