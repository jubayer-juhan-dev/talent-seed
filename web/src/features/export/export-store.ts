/** Shared state for the export dialog, opened from Explore (current filter) or the shortlist drawer. */
import { useSyncExternalStore } from "react";

export type ExportMode = "filter" | "shortlist";
type FilterContext = { query: Record<string, string | undefined>; total: number };
type State = { open: boolean; mode: ExportMode; filter: FilterContext | null };

let state: State = { open: false, mode: "filter", filter: null };
const listeners = new Set<() => void>();
const set = (patch: Partial<State>) => {
  state = { ...state, ...patch };
  for (const l of listeners) l();
};

export const exportDialog = {
  open: (mode: ExportMode) => set({ open: true, mode }),
  close: () => set({ open: false }),
  setMode: (mode: ExportMode) => set({ mode }),
  /** Explore keeps this current, so "current filter" means what's on screen. Null when Explore isn't shown. */
  setFilter: (filter: FilterContext | null) => {
    if (JSON.stringify(filter) !== JSON.stringify(state.filter)) set({ filter });
  },
};

export function useExportDialog() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => state,
  );
}
