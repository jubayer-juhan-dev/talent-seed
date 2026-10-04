import { useCallback, useEffect, useSyncExternalStore } from "react";
import { storage } from "@/lib/storage";

export type Theme = "light" | "dark";
const KEY = "ts.theme"; // null = follow the system
const media = () => window.matchMedia("(prefers-color-scheme: dark)");
const listeners = new Set<() => void>();

function current(): Theme {
  const saved = storage.get<Theme | null>(KEY, null);
  return saved ?? (media().matches ? "dark" : "light");
}

function apply() {
  document.documentElement.classList.toggle("dark", current() === "dark");
  for (const l of listeners) l();
}

/** Applies the theme before React renders, so there is no light flash in dark mode. */
export function initTheme() {
  apply();
  media().addEventListener("change", apply);
}

export function useTheme() {
  const theme = useSyncExternalStore((cb) => {
    listeners.add(cb);
    return () => listeners.delete(cb);
  }, current);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  const toggle = useCallback(() => {
    storage.set(KEY, current() === "dark" ? "light" : "dark");
    apply();
  }, []);
  return { theme, toggle };
}
