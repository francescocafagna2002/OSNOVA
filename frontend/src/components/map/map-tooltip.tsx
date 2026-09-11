import { formatPlz } from "@/lib/plz";

type MapTooltipProps = {
  plz: string | null;
  count: number;
  x: number;
  y: number;
  /** Width of the map container; when known, the tooltip flips left near the right edge. */
  containerWidth?: number;
};

const OFFSET = 12;
/** Room the tooltip needs to the right of the cursor before it flips to the left side. */
export const TOOLTIP_FLIP_MARGIN = 240;

/** Cursor-following label (spec R5); hidden when no PLZ is hovered. */
export function MapTooltip({ plz, count, x, y, containerWidth }: MapTooltipProps) {
  if (!plz) return null;
  const flipLeft = containerWidth !== undefined && containerWidth > 0 && x + TOOLTIP_FLIP_MARGIN > containerWidth;
  const position = flipLeft ? { right: containerWidth - x + OFFSET, top: y + OFFSET } : { left: x + OFFSET, top: y + OFFSET };
  return (
    <div
      role="tooltip"
      data-align={flipLeft ? "left" : "right"}
      className="pointer-events-none absolute z-10 rounded-[8px] border border-border bg-card px-2.5 py-1.5 text-[13px] leading-tight whitespace-nowrap shadow-[0_1px_3px_rgba(20,40,60,0.06)]"
      style={position}
    >
      <span className="font-medium text-navy">{formatPlz(plz)}</span>
      <span className="text-muted-foreground">
        {" · "}
        {count === 0 ? "No buildings" : `${count} ${count === 1 ? "building" : "buildings"}`}
      </span>
    </div>
  );
}
