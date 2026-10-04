import { createRootRoute, createRoute, createRouter, redirect, retainSearchParams } from "@tanstack/react-router";
import { AppShell } from "@/components/app/app-shell";
import { ExplorePage } from "@/features/explore/explore-page";
import { validateExploreSearch } from "@/features/explore/search";
import { OverviewPage } from "@/routes/overview";

/** `key` (the access key) is kept on every navigation, so reloads work even when cookies are blocked. */
const rootRoute = createRootRoute({
  validateSearch: (s: Record<string, unknown>): { key?: string } => (typeof s.key === "string" ? { key: s.key } : {}),
  search: { middlewares: [retainSearchParams(["key"])] },
  component: AppShell,
});

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  // First-viewer links put Explore on the root URL as ?view=explore&…; send them to /explore with the same filters.
  validateSearch: (s: Record<string, unknown>): { view?: string } => (s.view === "explore" ? { view: "explore" } : {}),
  beforeLoad: ({ location }) => {
    const { view, ...rest } = location.search as Record<string, unknown>;
    if (view === "explore") throw redirect({ to: "/explore", search: validateExploreSearch(rest), replace: true });
  },
  component: OverviewPage,
});

const exploreRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/explore",
  validateSearch: validateExploreSearch,
  component: ExplorePage,
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([overviewRoute, exploreRoute]),
  basepath: import.meta.env.BASE_URL.replace(/\/$/, "") || "/",
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
