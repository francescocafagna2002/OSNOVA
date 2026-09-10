import { formatPlz } from "@/lib/plz";

type MapTooltipProps = { plz: string | null; count: number; x: number; y: number };

/** Cursor-following label (spec R5); hidden when no PLZ is hovered. */
export function MapTooltip({ plz, count, x, y }: MapTooltipProps) {
  if (!plz) return null;
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 rounded-[8px] border border-border bg-card px-2.5 py-1.5 text-[13px] leading-tight shadow-[0_1px_3px_rgba(20,40,60,0.06)]"
      style={{ left: x + 12, top: y + 12 }}
    >
      <span className="font-medium text-navy">{formatPlz(plz)}</span>
      <span className="text-muted-foreground">
        {" · "}
        {count} {count === 1 ? "building" : "buildings"}
      </span>
    </div>
  );
}
