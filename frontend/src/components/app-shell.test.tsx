import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { makeBuilding } from "@/test/fixtures";
import { renderWithProviders } from "@/test/render";

const dynamicMock = vi.hoisted(() => vi.fn());

vi.mock("next/dynamic", () => ({
  default: (...args: unknown[]) => {
    dynamicMock(...args);
    function MapPlaceholder() {
      return <div data-testid="map-view" />;
    }
    return MapPlaceholder;
  },
}));

// `next/dynamic` is mocked above, so it never actually imports the real module — but
// guard against that changing (or the mock being bypassed) so this test never has to
// load maplibre-gl, which touches `window` at import time and is otherwise heavy.
vi.mock("@/components/map/map-view", () => ({
  MapView: () => <div data-testid="map-view" />,
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

  it("loads the map client-only, with server-side rendering disabled", async () => {
    renderWithProviders(<AppShell />);
    await screen.findByText("Building AG-000001");
    expect(dynamicMock).toHaveBeenCalledWith(
      expect.any(Function),
      expect.objectContaining({ ssr: false }),
    );
  });

  it("hides the map and widens the list in list mode", async () => {
    useUIStore.getState().setViewMode("list");
    renderWithProviders(<AppShell />);
    expect(screen.queryByTestId("map-view")).not.toBeInTheDocument();
    expect(screen.getByTestId("list-panel")).toHaveAttribute("data-mode", "list");
  });
});
