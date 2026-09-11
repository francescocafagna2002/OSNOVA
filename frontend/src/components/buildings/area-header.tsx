"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useFilteredBuildings } from "@/hooks/use-buildings";
import { formatPlz } from "@/lib/plz";
import { useUIStore } from "@/stores/ui-store";

export function AreaHeader() {
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const selectPlz = useUIStore((s) => s.selectPlz);
  const { total, isLoading } = useFilteredBuildings();
  const title = selectedPlz ? `Buildings in ${formatPlz(selectedPlz)}` : "Buildings in Aargau";
  const count = `${total} ${total === 1 ? "building" : "buildings"}`;
  return (
    <div className="flex items-start justify-between gap-2 border-b px-4 py-3">
      <div>
        <h2 className="text-lg text-navy">{title}</h2>
        <p className="text-[13px] text-muted-foreground">{isLoading ? "Loading…" : count}</p>
      </div>
      {selectedPlz && (
        <Button variant="outline" size="xs" onClick={() => selectPlz(null)}>
          <X />
          Show all areas
        </Button>
      )}
    </div>
  );
}
