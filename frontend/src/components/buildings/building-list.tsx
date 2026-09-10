"use client";

import { useEffect } from "react";

import { AreaHeader } from "@/components/buildings/area-header";
import { BuildingCard } from "@/components/buildings/building-card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useFilteredBuildings } from "@/hooks/use-buildings";
import { useUIStore } from "@/stores/ui-store";

export function BuildingList() {
  const { buildings, isLoading, isError } = useFilteredBuildings();
  const selectedBuildingId = useUIStore((s) => s.selectedBuildingId);
  const selectBuilding = useUIStore((s) => s.selectBuilding);
  const searchQuery = useUIStore((s) => s.searchQuery);

  useEffect(() => {
    if (!selectedBuildingId) return;
    document
      .getElementById(`building-card-${selectedBuildingId}`)
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedBuildingId]);

  const empty = !isLoading && !isError && buildings.length === 0;

  return (
    <section aria-label="Buildings" className="flex h-full min-h-0 flex-col">
      <AreaHeader />
      <ScrollArea className="min-h-0 flex-1">
        <div className="flex flex-col gap-2 p-3">
          {isLoading && <p className="p-4 text-sm text-muted-foreground">Loading buildings…</p>}
          {isError && <p className="p-4 text-sm text-destructive">Could not load buildings.</p>}
          {empty && (
            <p className="p-4 text-sm text-muted-foreground">
              {searchQuery ? `No buildings match “${searchQuery}”.` : "No buildings in this area."}
            </p>
          )}
          {buildings.map((building) => (
            <BuildingCard
              key={building.id}
              building={building}
              selected={building.id === selectedBuildingId}
              onSelect={selectBuilding}
            />
          ))}
        </div>
      </ScrollArea>
    </section>
  );
}
