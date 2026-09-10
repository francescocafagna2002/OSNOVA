import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { AppHeader } from "@/components/header/app-header";
import { initialUIState, useUIStore } from "@/stores/ui-store";
import { renderWithProviders } from "@/test/render";

describe("AppHeader", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("shows the wordmark, area and search placeholder", () => {
    renderWithProviders(<AppHeader />);
    expect(screen.getByText("Energy Fingerprints")).toBeInTheDocument();
    expect(screen.getByText("Aargau (AG)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search building ID, PLZ or town...")).toBeInTheDocument();
  });

  it("writes the search query to the store", async () => {
    renderWithProviders(<AppHeader />);
    await userEvent.type(screen.getByRole("searchbox", { name: "Search buildings" }), "aarau");
    expect(useUIStore.getState().searchQuery).toBe("aarau");
  });

  it("toggles the view mode with pressed state", async () => {
    renderWithProviders(<AppHeader />);
    const list = screen.getByRole("button", { name: "List" });
    const map = screen.getByRole("button", { name: "Map" });
    expect(map).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(list);
    expect(useUIStore.getState().viewMode).toBe("list");
    expect(list).toHaveAttribute("aria-pressed", "true");
    expect(map).toHaveAttribute("aria-pressed", "false");
  });

  it("opens the about dialog flag", async () => {
    renderWithProviders(<AppHeader />);
    await userEvent.click(screen.getByRole("button", { name: "About this project" }));
    expect(useUIStore.getState().isAboutOpen).toBe(true);
  });
});
