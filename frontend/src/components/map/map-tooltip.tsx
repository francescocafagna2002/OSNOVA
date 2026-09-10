import { formatPlz } from "@/lib/plz";

type MapTooltipProps = { plz: string | null; count: number; x: number; y: number };

/** Cursor-following label; hidden when no PLZ is hovered. */
export function MapTooltip({ plz, count, x, y }: MapTooltipProps) {
  if (!plz) return null;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 rounded-md border bg-background/95 px-2 py-1 text-xs shadow-sm"
      style={{ left: x + 12, top: y + 12 }}
    >
      {formatPlz(plz)} · {count} {count === 1 ? "building" : "buildings"}
    </div>
  );
}
