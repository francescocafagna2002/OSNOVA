"use client";

import dynamic from "next/dynamic";

import { BuildingList } from "@/components/buildings/building-list";
import { BuildingDetailSheet } from "@/components/detail/building-detail-sheet";
import { AboutDialog } from "@/components/header/about-dialog";
import { AppHeader } from "@/components/header/app-header";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

/** MapLibre touches `window` at import time; load it on the client only (spec D2). */
const MapView = dynamic(() => import("@/components/map/map-view").then((m) => m.MapView), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-muted" aria-label="Loading map" />,
});

/**
 * Layout per spec D12: desktop map mode = map 65 / list 35; desktop list mode = list
 * full width; mobile shows exactly one of the two.
 */
export function AppShell() {
  const viewMode = useUIStore((s) => s.viewMode);
  const showMap = viewMode === "map";

  return (
    <div className="flex h-dvh flex-col">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        {showMap && (
          <div className="relative min-h-0 flex-1 lg:basis-[65%]">
            <MapView />
          </div>
        )}
        <aside
          data-testid="list-panel"
          data-mode={viewMode}
          className={cn(
            "min-h-0 bg-background",
            showMap ? "hidden border-l lg:flex lg:w-[35%] lg:max-w-md lg:flex-col" : "flex flex-1 flex-col",
          )}
        >
          <BuildingList />
        </aside>
      </div>
      <BuildingDetailSheet />
      <AboutDialog />
    </div>
  );
}
