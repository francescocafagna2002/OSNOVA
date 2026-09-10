"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { fetchBuildings } from "@/lib/api";
import { countBuildingsByPlz } from "@/lib/plz";
import { filterBuildings } from "@/lib/search";
import type { Building } from "@/lib/types";
import { useUIStore } from "@/stores/ui-store";

const buildingsQueryKey = ["buildings"] as const;

const EMPTY: Building[] = [];

export function useBuildings() {
  return useQuery({ queryKey: buildingsQueryKey, queryFn: fetchBuildings, staleTime: Infinity });
}

/** PLZ filter first, then search. `total` is the area count before search. */
export function useFilteredBuildings() {
  const { data, isLoading, isError } = useBuildings();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  const searchQuery = useUIStore((s) => s.searchQuery);
  const inArea = useMemo(() => {
    const all = data ?? EMPTY;
    return selectedPlz ? all.filter((b) => b.postcode === selectedPlz) : all;
  }, [data, selectedPlz]);
  const buildings = useMemo(() => filterBuildings(inArea, searchQuery), [inArea, searchQuery]);
  return { buildings, total: inArea.length, isLoading, isError };
}

export function useSelectedBuilding(): Building | undefined {
  const { data } = useBuildings();
  const id = useUIStore((s) => s.selectedBuildingId);
  return useMemo(() => (id ? data?.find((b) => b.id === id) : undefined), [data, id]);
}

/** Counts over the whole dataset, independent of filters; feeds the map tooltip. */
export function usePlzCounts(): Record<string, number> {
  const { data } = useBuildings();
  return useMemo(() => countBuildingsByPlz(data ?? EMPTY), [data]);
}

/** The PLZ the map should outline: the selected building's, else the selected area. */
export function useHighlightedPlz(): string | null {
  const selected = useSelectedBuilding();
  const selectedPlz = useUIStore((s) => s.selectedPlz);
  return selected?.postcode ?? selectedPlz;
}
