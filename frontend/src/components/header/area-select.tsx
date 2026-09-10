"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/** Static for the prototype: Aargau is the only area with data. */
export const AREAS = [{ value: "AG", label: "Aargau (AG)" }] as const;

export function AreaSelect() {
  return (
    <Select value="AG" items={AREAS}>
      <SelectTrigger aria-label="Area" className="w-40">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {AREAS.map((area) => (
          <SelectItem key={area.value} value={area.value}>
            {area.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
