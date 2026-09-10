"use client";

import { BuildingList } from "@/components/buildings/building-list";
import { useUIStore } from "@/stores/ui-store";

/** Throwaway preview for the list task; deleted at integration. */
export default function ListPreviewPage() {
  const state = useUIStore();
  return (
    <div className="flex h-dvh">
      <div className="flex-1 space-y-2 p-4 text-sm">
        <button className="rounded border px-2 py-1" onClick={() => state.selectPlz("5000")}>Select 5000</button>
        <button className="ml-2 rounded border px-2 py-1" onClick={() => state.setSearchQuery("baden")}>Search baden</button>
        <pre className="text-xs text-muted-foreground">
          {JSON.stringify({ selectedPlz: state.selectedPlz, selectedBuildingId: state.selectedBuildingId, isDetailOpen: state.isDetailOpen }, null, 2)}
        </pre>
      </div>
      <aside className="w-[400px] border-l">
        <BuildingList />
      </aside>
    </div>
  );
}
