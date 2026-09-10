"use client";

import { Building2 } from "lucide-react";

import { ProbabilityChip } from "@/components/buildings/probability-chip";
import { ASSETS } from "@/lib/predictions";
import type { Building } from "@/lib/types";
import { cn } from "@/lib/utils";

type BuildingCardProps = { building: Building; selected: boolean; onSelect: (id: string) => void };

export function BuildingCard({ building, selected, onSelect }: BuildingCardProps) {
  return (
    <button
      type="button"
      id={`building-card-${building.id}`}
      aria-pressed={selected}
      onClick={() => onSelect(building.id)}
      className={cn(
        "w-full rounded-xl bg-card p-3 text-left ring-1 ring-foreground/10 transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        selected && "bg-primary/5 ring-2 ring-primary hover:bg-primary/5",
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className="grid size-8 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
          <Building2 className="size-4" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">Building {building.id}</div>
          <div className="text-xs text-muted-foreground">
            {building.postcode} {building.city}
          </div>
        </div>
      </div>
      <div className="mt-2.5 flex flex-wrap gap-1.5">
        {ASSETS.map((asset) => (
          <ProbabilityChip key={asset.key} assetKey={asset.key} probability={building.predictions[asset.key]} />
        ))}
      </div>
    </button>
  );
}
