import { hexToRgba, LINE_COLOR } from "@/lib/chart-option";
import { EVENT_META } from "@/lib/events";
import type { BuildingEvent, BuildingEventType } from "@/lib/types";

export function ChartLegend({ events }: { events: BuildingEvent[] }) {
  const types = Array.from(new Set<BuildingEventType>(events.map((event) => event.type)));
  return (
    <ul aria-label="Chart legend" className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="inline-block h-[2px] w-[14px] rounded" style={{ backgroundColor: LINE_COLOR }} />
        Net power
      </li>
      {types.map((type) => (
        <li key={type} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block size-[10px] rounded-sm"
            style={{ backgroundColor: hexToRgba(EVENT_META[type].color, 0.35) }}
          />
          {EVENT_META[type].label}
        </li>
      ))}
    </ul>
  );
}
