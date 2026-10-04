/** Starred people, kept in this browser. Same storage key and shape as the first viewer, so lists carry over. */
import { useSyncExternalStore } from "react";
import { storage } from "./storage";

export type ShortlistEntry = {
  person_id: string;
  display_name?: string | null;
  github_login?: string | null;
  github_user_id?: number | null;
  priority_cohort?: string | null;
  country?: string | null;
};

const KEY = "ts.shortlist";
const listeners = new Set<() => void>();
let entries: ShortlistEntry[] = storage.get<ShortlistEntry[]>(KEY, []);

function save(next: ShortlistEntry[]) {
  entries = next;
  storage.set(KEY, entries);
  for (const l of listeners) l();
}

export const shortlist = {
  has: (id: string) => entries.some((e) => e.person_id === id),
  toggle(p: ShortlistEntry) {
    save(shortlist.has(p.person_id) ? entries.filter((e) => e.person_id !== p.person_id) : [...entries, p]);
  },
  remove: (id: string) => save(entries.filter((e) => e.person_id !== id)),
  clear: () => save([]),
};

export function useShortlist() {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => entries,
  );
}
