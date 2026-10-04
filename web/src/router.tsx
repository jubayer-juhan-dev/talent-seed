import { createRootRoute, createRoute, createRouter, retainSearchParams } from "@tanstack/react-router";
import { AppShell } from "@/components/app/app-shell";
import { ExplorePage } from "@/routes/explore";
import { OverviewPage } from "@/routes/overview";

/** `key` (the access key) is kept on every navigation, so reloads work even when cookies are blocked. */
const rootRoute = createRootRoute({
  validateSearch: (s: Record<string, unknown>): { key?: string } => (typeof s.key === "string" ? { key: s.key } : {}),
  search: { middlewares: [retainSearchParams(["key"])] },
  component: AppShell,
});

const overviewRoute = createRoute({ getParentRoute: () => rootRoute, path: "/", component: OverviewPage });
const exploreRoute = createRoute({ getParentRoute: () => rootRoute, path: "/explore", component: ExplorePage });

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
