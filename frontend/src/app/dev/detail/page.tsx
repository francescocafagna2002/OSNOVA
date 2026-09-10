"use client";

import { BuildingDetailSheet } from "@/components/detail/building-detail-sheet";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the detail task; deleted at integration. */
export default function DetailPreviewPage() {
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  return (
    <div className="p-6">
      <button className="rounded border px-3 py-1.5 text-sm" onClick={() => selectBuilding("AG-004711")}>
        Open demo building
      </button>
      <BuildingDetailSheet />
    </div>
  );
}
