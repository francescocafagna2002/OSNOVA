import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuildingList } from "@/components/buildings/building-list";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

// jsdom has no Element.getAnimations; base-ui's ScrollArea viewport calls it on an
// internal timeout. Polyfilled here (not in the shared test/setup.ts, which this
// task does not own) — see "Requests for Task 10" in the task-7 report.
if (!Element.prototype.getAnimations) {
  Element.prototype.getAnimations = () => [];
}

vi.mock("@/lib/api", () => ({
  fetchBuildings: async () => [
    makeBuilding({ id: "AG-000001", postcode: "5000", city: "Aarau" }),
    makeBuilding({ id: "AG-000002", postcode: "5000", city: "Aarau" }),
    makeBuilding({ id: "AG-000003", postcode: "5400", city: "Baden" }),
  ],
}));

describe("BuildingList", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("lists all buildings with the canton header", async () => {
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buildings in Aargau" })).toBeInTheDocument();
    expect(screen.getByText("3 buildings")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show all areas/ })).not.toBeInTheDocument();
  });

  it("filters to the selected area and offers to show all", async () => {
    useUIStore.getState().selectPlz("5400");
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("Building AG-000003")).toBeInTheDocument();
    expect(screen.queryByText("Building AG-000001")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Buildings in 5400 Baden" })).toBeInTheDocument();
    expect(screen.getByText("1 building")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show all areas/ }));
    expect(useUIStore.getState().selectedPlz).toBeNull();
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
  });

  it("selects a building on click and scrolls the selected card into view", async () => {
    const scrollSpy = vi.spyOn(Element.prototype, "scrollIntoView");
    renderWithProviders(<BuildingList />);
    await userEvent.click(await screen.findByText("Building AG-000002"));
    const state = useUIStore.getState();
    expect(state.selectedBuildingId).toBe("AG-000002");
    expect(state.isDetailOpen).toBe(true);
    await waitFor(() => expect(screen.getByRole("button", { pressed: true })).toHaveAttribute("id", "building-card-AG-000002"));
    expect(scrollSpy).toHaveBeenCalled();
  });

  it("shows an empty state for a search with no matches", async () => {
    useUIStore.getState().setSearchQuery("zzz");
    renderWithProviders(<BuildingList />);
    expect(await screen.findByText("No buildings match “zzz”.")).toBeInTheDocument();
  });
});
