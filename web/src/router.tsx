import { createRootRoute, createRoute, createRouter, redirect, retainSearchParams } from "@tanstack/react-router";
import { AppShell } from "@/components/app/app-shell";
import { ExplorePage } from "@/features/explore/explore-page";
import { validateExploreSearch } from "@/features/explore/search";
import { JobDetailPage } from "@/features/jobs/job-detail-page";
import { JobsPage } from "@/features/jobs/jobs-page";
import { OverviewPage } from "@/features/overview/overview-page";

/** `key` (the access key) is kept on every navigation, so reloads work even when cookies are blocked. */
const rootRoute = createRootRoute({
  validateSearch: (s: Record<string, unknown>): { key?: string } => (typeof s.key === "string" ? { key: s.key } : {}),
  search: { middlewares: [retainSearchParams(["key"])] },
  component: AppShell,
});

/** First-viewer profile links ended in #p=<id>; the new app uses ?p=<id>. */
const profileFromHash = (hash: string) => (hash.startsWith("p=") ? decodeURIComponent(hash.slice(2)) : undefined);

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  // First-viewer links put Explore on the root URL as ?view=explore&…; send them to /explore with the same filters.
  validateSearch: (s: Record<string, unknown>): { view?: string } => (s.view === "explore" ? { view: "explore" } : {}),
  beforeLoad: ({ location }) => {
    const { view, ...rest } = location.search as Record<string, unknown>;
    const p = profileFromHash(location.hash);
    if (view === "explore" || p)
      throw redirect({ to: "/explore", search: { ...validateExploreSearch(rest), ...(p && { p }) }, replace: true });
  },
  component: OverviewPage,
});

const jobsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs",
  component: JobsPage,
});

function JobDetailRoute() {
  const { jobId } = jobDetailRoute.useParams();
  return <JobDetailPage jobId={jobId} />;
}

const jobDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/jobs/$jobId",
  component: JobDetailRoute,
});

const exploreRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/explore",
  validateSearch: validateExploreSearch,
  beforeLoad: ({ location, search }) => {
    const p = profileFromHash(location.hash);
    if (p) throw redirect({ to: "/explore", search: { ...search, p }, hash: "", replace: true });
  },
  component: ExplorePage,
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([overviewRoute, exploreRoute, jobsRoute, jobDetailRoute]),
  basepath: import.meta.env.BASE_URL.replace(/\/$/, "") || "/",
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
