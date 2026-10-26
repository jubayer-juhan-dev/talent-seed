/** Explore's URL search params. Same names and value formats as the first viewer, so old links keep working:
 *  lists are comma-separated, except `eco` which uses "|" (project names can contain commas). */

export const SORTS = [
  {
    key: "active_days",
    dir: "desc",
    label: "Most active",
    hint: "Days with commits in the last 84 days",
    phrase: "days active in the last 84",
  },
  { key: "last_activity", dir: "desc", label: "Recently active", hint: "Latest commit date", phrase: "latest commit" },
  {
    key: "first_commit",
    dir: "asc",
    label: "Longest history",
    hint: "Earliest first commit",
    phrase: "earliest first commit",
  },
  {
    key: "ecosystems",
    dir: "desc",
    label: "Most ecosystems",
    hint: "Chains and projects worked on",
    phrase: "chains and projects",
  },
  { key: "repos", dir: "desc", label: "Most repos", hint: "Includes forks", phrase: "repo count" },
  {
    key: "commits",
    dir: "desc",
    label: "Most commits",
    hint: "Inflated by forks and copied history",
    phrase: "commit count",
  },
  { key: "name", dir: "asc", label: "Name A–Z", hint: "", phrase: "name" },
] as const;
export type SortKey = (typeof SORTS)[number]["key"];
export type Dir = "asc" | "desc";

export const LIST_FILTERS = ["eco", "activity", "tenure", "exclusivity", "country", "ai_enriched"] as const;
export type ListFilter = (typeof LIST_FILTERS)[number];
const SEP: Record<ListFilter, string> = {
  eco: "|",
  activity: ",",
  tenure: ",",
  exclusivity: ",",
  country: ",",
  ai_enriched: ",",
};

export type ExploreSearch = {
  /** "P1" (default), "P2", "P3", "HOLD", "P1,P2,P3", or "all". */
  cohort?: string;
  q?: string;
  eco?: string;
  activity?: string;
  tenure?: string;
  exclusivity?: string;
  country?: string;
  /** "yes" AI-enriched only, "no" not AI-enriched; both or neither = everyone. */
  ai_enriched?: string;
  /** "show" includes probable bots and GitHub conflicts (hidden by default). */
  flagged?: "show";
  sort?: SortKey;
  dir?: Dir;
  layout?: "table";
  /** Person whose profile is open (plan step 4). */
  p?: string;
};

export const DEFAULTS = { cohort: "P1", sort: "active_days", dir: "desc" } as const;

const str = (v: unknown) => (v == null || v === "" ? undefined : String(v));

export function validateExploreSearch(s: Record<string, unknown>): ExploreSearch {
  const sort = SORTS.find((x) => x.key === s.sort)?.key;
  // Old links used an empty cohort= for "all cohorts".
  const cohort = s.cohort === "" ? "all" : str(s.cohort);
  return {
    cohort: cohort === DEFAULTS.cohort ? undefined : cohort,
    q: str(s.q),
    eco: str(s.eco),
    activity: str(s.activity),
    tenure: str(s.tenure),
    exclusivity: str(s.exclusivity),
    country: str(s.country),
    ai_enriched: str(s.ai_enriched),
    flagged: s.flagged === "show" ? "show" : undefined,
    sort: sort === DEFAULTS.sort ? undefined : sort,
    dir: s.dir === "asc" || s.dir === "desc" ? s.dir : undefined,
    layout: s.layout === "table" ? "table" : undefined,
    p: str(s.p),
  };
}

export const listOf = (s: ExploreSearch, k: ListFilter) => (s[k] ?? "").split(SEP[k]).filter(Boolean);
export const joinList = (k: ListFilter, values: string[]) => (values.length ? values.join(SEP[k]) : undefined);

export const sortOf = (s: ExploreSearch) => SORTS.find((x) => x.key === (s.sort ?? DEFAULTS.sort)) ?? SORTS[0];
export const dirOf = (s: ExploreSearch): Dir => s.dir ?? sortOf(s).dir;

/** The API takes ai_enriched=1 or 0; the URL uses yes/no (plain numbers would be JSON-quoted by the router). */
function aiParam(s: ExploreSearch) {
  const v = listOf(s, "ai_enriched");
  if (v.length !== 1) return undefined;
  return v[0] === "yes" ? "1" : v[0] === "no" ? "0" : undefined;
}

/** Query params for /api/people and /api/export.csv. */
export function apiQuery(s: ExploreSearch) {
  const cohort = s.cohort ?? DEFAULTS.cohort;
  return {
    cohort: cohort === "all" ? undefined : cohort,
    q: s.q,
    eco: s.eco,
    activity: s.activity,
    tenure: s.tenure,
    exclusivity: s.exclusivity,
    country: s.country,
    ai_enriched: aiParam(s),
    hide_flagged: s.flagged === "show" ? undefined : "1",
    sort: s.sort ?? DEFAULTS.sort,
    dir: dirOf(s),
  };
}
