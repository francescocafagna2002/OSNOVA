"use client";

import { List as ListIcon, Map as MapIcon, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ViewMode } from "@/stores/ui-store";

const OPTIONS: { value: ViewMode; label: string; icon: LucideIcon }[] = [
  { value: "map", label: "Map", icon: MapIcon },
  { value: "list", label: "List", icon: ListIcon },
];

export function ViewToggle({ value, onChange }: { value: ViewMode; onChange: (mode: ViewMode) => void }) {
  return (
    <div role="group" aria-label="View" className="flex rounded-lg border border-border bg-card p-0.5">
      {OPTIONS.map(({ value: mode, label, icon: Icon }) => {
        const active = value === mode;
        return (
          <Button
            key={mode}
            size="sm"
            variant="ghost"
            aria-pressed={active}
            onClick={() => onChange(mode)}
            className={cn("h-7 px-2.5", active && "bg-accent text-navy hover:bg-accent")}
          >
            <Icon />
            {label}
          </Button>
        );
      })}
    </div>
  );
}
