import { ASSET_BY_KEY } from "@/lib/predictions";
import type { BuildingEventType } from "@/lib/types";

export type EventMeta = { label: string; color: string };

export const EVENT_META: Record<BuildingEventType, EventMeta> = {
  ev_charging: { label: "EV charging", color: ASSET_BY_KEY.ev.color },
  pv_generation: { label: "Possible PV generation", color: ASSET_BY_KEY.pv.color },
  high_consumption: { label: "High consumption", color: "#64748b" },
};

/** Fill alpha for chart bands; keeps the consumption line the primary element. */
export const EVENT_BAND_OPACITY = 0.14;
