"use client";

import dynamic from "next/dynamic";

import { useUIStore } from "@/stores/ui-store";

const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), { ssr: false });

/** Throwaway preview for the map task; deleted at integration. */
export default function MapPreviewPage() {
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  return (
    <div className="flex h-dvh flex-col">
      <div className="flex items-center gap-3 border-b px-4 py-2 text-sm">
        <span>selectedPlz: {selectedPlz ?? "none"}</span>
        <button className="rounded border px-2 py-1" onClick={() => selectBuilding("AG-004711")}>
          Select demo building
        </button>
      </div>
      <div className="min-h-0 flex-1">
        <MapView />
      </div>
    </div>
  );
}
