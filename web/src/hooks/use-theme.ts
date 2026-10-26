/** The app uses the Nocturne design system, which is dark only. The `dark` class stays on <html> so shadcn's
 *  `dark:` variants keep resolving. */
export type Theme = "dark";

export function initTheme() {
  document.documentElement.classList.add("dark");
}

export function useTheme() {
  return { theme: "dark" as Theme };
}
