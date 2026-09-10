import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

vi.mock("next/dynamic", () => ({
  default: () => {
    function MapPlaceholder() {
      return <div data-testid="map-view" />;
    }
    return MapPlaceholder;
  },
}));

vi.mock("@/lib/api", () => ({ fetchBuildings: async () => [makeBuilding()] }));

describe("AppShell", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("shows header, map and list in map mode", async () => {
    renderWithProviders(<AppShell />);
    expect(screen.getByText("Energy Fingerprints")).toBeInTheDocument();
    expect(screen.getByTestId("map-view")).toBeInTheDocument();
    expect(await screen.findByText("Building AG-000001")).toBeInTheDocument();
    expect(screen.getByTestId("list-panel")).toHaveAttribute("data-mode", "map");
  });

  it("hides the map and widens the list in list mode", async () => {
    useUIStore.getState().setViewMode("list");
    renderWithProviders(<AppShell />);
    expect(screen.queryByTestId("map-view")).not.toBeInTheDocument();
    expect(screen.getByTestId("list-panel")).toHaveAttribute("data-mode", "list");
  });
});
