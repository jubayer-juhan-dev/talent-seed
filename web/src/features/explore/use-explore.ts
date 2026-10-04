import { getRouteApi } from "@tanstack/react-router";
import type { ExploreSearch } from "./search";

const route = getRouteApi("/explore");

/** Explore's state lives in the URL. `update` merges a patch and replaces the history entry, so filtering
 *  doesn't fill the back button (opening a profile pushes, see plan step 4). */
export function useExplore() {
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const update = (patch: Partial<ExploreSearch>, opts: { push?: boolean } = {}) =>
    navigate({ search: (prev) => ({ ...prev, ...patch }), replace: !opts.push });
  return { search, update };
}
