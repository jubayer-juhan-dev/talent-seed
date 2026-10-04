/** Lets the top-bar "?" button (re)start the tour mounted in AppShell. */
const listeners = new Set<() => void>();
export const tour = {
  start: () => {
    for (const l of listeners) l();
  },
  onStart: (l: () => void) => {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  },
};
