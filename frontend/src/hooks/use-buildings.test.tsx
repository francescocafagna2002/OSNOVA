import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QueryClientProvider } from "@tanstack/react-query";

import { useFilteredBuildings, useHighlightedPlz, usePlzCounts, useSelectedBuilding } from "@/hooks/use-buildings";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { createTestQueryClient } from "@/test/render";

const fixtures = [
  makeBuilding({ id: "AG-000001", postcode: "5000", city: "Aarau" }),
  makeBuilding({ id: "AG-000002", postcode: "5000", city: "Aarau" }),
  makeBuilding({ id: "AG-000003", postcode: "5400", city: "Baden" }),
];

vi.mock("@/lib/api", () => ({ fetchBuildings: async () => fixtures }));

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

describe("use-buildings hooks", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("filters by selected PLZ first, then by search, and reports the area total", async () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().setSearchQuery("000002");
    const { result } = renderHook(() => useFilteredBuildings(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.buildings.map((b) => b.id)).toEqual(["AG-000002"]);
    expect(result.current.total).toBe(2);
  });

  it("returns all buildings when no area is selected", async () => {
    const { result } = renderHook(() => useFilteredBuildings(), { wrapper });
    await waitFor(() => expect(result.current.buildings.length).toBe(3));
    expect(result.current.total).toBe(3);
  });

  it("resolves the selected building and its PLZ as the highlight", async () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().selectBuilding("AG-000003");
    const selected = renderHook(() => useSelectedBuilding(), { wrapper });
    await waitFor(() => expect(selected.result.current?.id).toBe("AG-000003"));
    const highlighted = renderHook(() => useHighlightedPlz(), { wrapper });
    await waitFor(() => expect(highlighted.result.current).toBe("5400"));
  });

  it("falls back to the selected area when no building is selected", () => {
    useUIStore.getState().selectPlz("5000");
    const { result } = renderHook(() => useHighlightedPlz(), { wrapper });
    expect(result.current).toBe("5000");
  });

  it("counts buildings per PLZ over the whole dataset", async () => {
    useUIStore.getState().selectPlz("5400");
    const { result } = renderHook(() => usePlzCounts(), { wrapper });
    await waitFor(() => expect(result.current).toEqual({ "5000": 2, "5400": 1 }));
  });
});
