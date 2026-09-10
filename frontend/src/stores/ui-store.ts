import { create } from "zustand";

export type ViewMode = "map" | "list";

/**
 * Ephemeral UI state only. Building data lives in TanStack Query; derived values
 * (filtered list, selected building, highlighted PLZ) live in hooks, never here.
 */
interface UIStateSlice {
  /** Area filter chosen on the map or cleared via "Show all areas". */
  selectedPlz: string | null;
  selectedBuildingId: string | null;
  isDetailOpen: boolean;
  viewMode: ViewMode;
  searchQuery: string;
  isAboutOpen: boolean;
}

interface UIActions {
  /** Sets the area filter, clears any selected building, closes the detail. */
  selectPlz: (plz: string | null) => void;
  /** Selects a building and opens the detail; leaves the area filter alone. */
  selectBuilding: (id: string) => void;
  /** Closes the detail but keeps the building highlighted. */
  closeDetail: () => void;
  clearSelection: () => void;
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setAboutOpen: (open: boolean) => void;
}

type UIState = UIStateSlice & UIActions;

export const initialUIState: UIStateSlice = {
  selectedPlz: null,
  selectedBuildingId: null,
  isDetailOpen: false,
  viewMode: "map",
  searchQuery: "",
  isAboutOpen: false,
};

export const useUIStore = create<UIState>((set) => ({
  ...initialUIState,
  selectPlz: (plz) => set({ selectedPlz: plz, selectedBuildingId: null, isDetailOpen: false }),
  selectBuilding: (id) => set({ selectedBuildingId: id, isDetailOpen: true }),
  closeDetail: () => set({ isDetailOpen: false }),
  clearSelection: () => set({ selectedBuildingId: null, isDetailOpen: false }),
  setViewMode: (mode) => set({ viewMode: mode }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setAboutOpen: (open) => set({ isAboutOpen: open }),
}));
