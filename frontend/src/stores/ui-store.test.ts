import { beforeEach, describe, expect, it } from "vitest";

import { initialUIState, useUIStore } from "@/stores/ui-store";

describe("ui-store", () => {
  beforeEach(() => {
    useUIStore.setState(initialUIState);
  });

  it("starts with nothing selected, map view, empty search", () => {
    const s = useUIStore.getState();
    expect(s.selectedPlz).toBeNull();
    expect(s.selectedBuildingId).toBeNull();
    expect(s.isDetailOpen).toBe(false);
    expect(s.viewMode).toBe("map");
    expect(s.searchQuery).toBe("");
    expect(s.isAboutOpen).toBe(false);
  });

  it("selectBuilding sets the id and opens the detail without touching the area", () => {
    useUIStore.getState().selectPlz("5000");
    useUIStore.getState().selectBuilding("AG-004711");
    const s = useUIStore.getState();
    expect(s.selectedBuildingId).toBe("AG-004711");
    expect(s.isDetailOpen).toBe(true);
    expect(s.selectedPlz).toBe("5000");
  });

  it("selectPlz clears the building and closes the detail", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().selectPlz("5400");
    const s = useUIStore.getState();
    expect(s.selectedPlz).toBe("5400");
    expect(s.selectedBuildingId).toBeNull();
    expect(s.isDetailOpen).toBe(false);
  });

  it("closeDetail keeps the selection highlighted", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().closeDetail();
    const s = useUIStore.getState();
    expect(s.isDetailOpen).toBe(false);
    expect(s.selectedBuildingId).toBe("AG-004711");
  });

  it("clearSelection drops the building and closes the detail", () => {
    useUIStore.getState().selectBuilding("AG-004711");
    useUIStore.getState().clearSelection();
    const s = useUIStore.getState();
    expect(s.isDetailOpen).toBe(false);
    expect(s.selectedBuildingId).toBeNull();
  });

  it("setters update view mode, search and about", () => {
    useUIStore.getState().setViewMode("list");
    useUIStore.getState().setSearchQuery("aarau");
    useUIStore.getState().setAboutOpen(true);
    const s = useUIStore.getState();
    expect(s.viewMode).toBe("list");
    expect(s.searchQuery).toBe("aarau");
    expect(s.isAboutOpen).toBe(true);
  });
});
