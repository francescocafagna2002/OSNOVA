import { ASSET_BY_KEY } from "@/lib/predictions";
import { BRAND, NEUTRAL } from "@/lib/theme";
import type { BuildingEventType } from "@/lib/types";

export type EventMeta = { label: string; color: string };

export const EVENT_META: Record<BuildingEventType, EventMeta> = {
  ev_charging: { label: "EV charging", color: BRAND.blue },
  pv_generation: { label: "Possible PV generation", color: ASSET_BY_KEY.pv.color },
  heat_pump_heating: { label: "Heat pump heating", color: ASSET_BY_KEY.heatPump.color },
  battery_cycle: { label: "Battery charging / discharging", color: ASSET_BY_KEY.battery.color },
  high_consumption: { label: "High consumption", color: NEUTRAL.textSecondary },
};
