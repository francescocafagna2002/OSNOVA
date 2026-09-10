import { create } from "zustand";

/**
 * Global UI state. Kept intentionally small — colocate feature state in its own
 * store rather than growing this one. Server data belongs in TanStack Query,
 * not here.
 */
interface UIState {
  /** Currently inspected customer/meter, or null when none is selected. */
  selectedCustomerId: string | null;
  setSelectedCustomerId: (id: string | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  selectedCustomerId: null,
  setSelectedCustomerId: (id) => set({ selectedCustomerId: id }),
}));
