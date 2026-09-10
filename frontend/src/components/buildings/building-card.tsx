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
        "w-full rounded-lg border border-border bg-card p-4 text-left shadow-[0_1px_3px_rgba(20,40,60,0.06)] transition-[border-color,background-color,box-shadow] duration-200 ease-out hover:border-[#AFC2D8] hover:bg-[#FBFDFF] focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:outline-none",
        selected && "border-primary bg-[#F7FBFE] shadow-[0_0_0_1px_#0065A8] hover:border-primary hover:bg-[#F7FBFE]",
      )}
    >
      <div className="flex items-start gap-2.5">
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-navy">
          <Building2 className="size-[18px]" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate font-serif text-[17px] font-semibold text-navy">Building {building.id}</div>
          <div className="text-[13px] text-muted-foreground">
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
