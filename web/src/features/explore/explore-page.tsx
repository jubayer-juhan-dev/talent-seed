import { useRouter } from "@tanstack/react-router";
import { ChevronDown, Download, LayoutGrid, Loader2, Rows3, SearchX, ServerCrash, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { exportDialog } from "@/features/export/export-store";
import { PersonProfile } from "@/features/profile/person-profile";
import { markProfilePushed, takeProfilePushed } from "@/features/profile/profile-nav";
import { fmt } from "@/lib/format";
import { useShortlist } from "@/lib/shortlist";
import { cn } from "@/lib/utils";
import { CohortSwitcher } from "./cohort-switcher";
import { FilterChips } from "./filter-chips";
import { FilterMenu } from "./filter-menu";
import { PeopleTable } from "./people-table";
import { PersonCard } from "./person-card";
import { apiQuery, dirOf, sortOf } from "./search";
import { SearchInput } from "./search-input";
import { SortMenu } from "./sort-menu";
import { useExplore } from "./use-explore";

export function ExplorePage() {
  const { search, update } = useExplore();
  const layout = search.layout ?? "cards";
  const query = $api.useInfiniteQuery(
    "get",
    "/api/people",
    { params: { query: apiQuery(search) } },
    {
      pageParamName: "page",
      initialPageParam: 1,
      getNextPageParam: (last) => (last.page * last.page_size < last.total ? last.page + 1 : undefined),
    },
  );
  const rows = query.data?.pages.flatMap((p) => p.rows) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;
  const router = useRouter();

  // Keep the export dialog's "current filter" in step with what's on screen.
  const exportQuery = JSON.stringify(apiQuery(search));
  useEffect(() => {
    exportDialog.setFilter({ query: JSON.parse(exportQuery), total });
  }, [exportQuery, total]);
  useEffect(() => () => exportDialog.setFilter(null), []);
  const list = useShortlist();
  const open = (id: string) => {
    markProfilePushed();
    update({ p: id }, { push: true });
  };
  // ←/→ step through the loaded results, or through the shortlist when the profile was opened from there.
  const ids = rows.map((r) => r.person_id);
  const shortlistIds = list.map((e) => e.person_id);
  const navIds = search.p && !ids.includes(search.p) && shortlistIds.includes(search.p) ? shortlistIds : ids;

  const sort = sortOf(search);
  return (
    <div className="animate-in duration-300 fade-in slide-in-from-bottom-1">
      <header className="mb-7 flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="mb-2 text-3xl font-medium tracking-[-0.025em] sm:text-[40px] sm:leading-[1.1]">Explore</h1>
          <div
            data-testid="result-summary"
            className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] text-muted-foreground"
            aria-live="polite"
          >
            <span>
              {query.isPending ? (
                "Searching…"
              ) : query.isError ? null : (
                <>
                  <span className="text-foreground tabular-nums">{fmt(total)}</span>{" "}
                  {total === 1 ? "person matches" : "people match"} · sorted by {sort.phrase}
                  {dirOf(search) !== sort.dir && " (reversed)"}
                </>
              )}
            </span>
            {search.sort === "commits" && (
              <span className="flex items-center gap-1.5 text-[13px]">
                <TriangleAlert className="size-3.5" /> Commit counts include forks and copied history
              </span>
            )}
          </div>
        </div>
        <Button data-tour="export" variant="outline" size="lg" onClick={() => exportDialog.open("filter")}>
          <Download className="size-4" />
          Export
        </Button>
      </header>

      <div className="mb-7 flex flex-col gap-4">
        <div data-tour="cohorts">
          <CohortSwitcher />
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <SearchInput />
          <div data-tour="filter">
            <FilterMenu />
          </div>
          <div data-tour="sort">
            <SortMenu />
          </div>
          <label
            htmlFor="hide-flagged"
            className="flex cursor-pointer items-center gap-2 px-1.5 text-[13px] text-muted-foreground select-none"
          >
            <input
              id="hide-flagged"
              type="checkbox"
              checked={search.flagged !== "show"}
              onChange={(e) => update({ flagged: e.target.checked ? undefined : "show" })}
              className="size-3.5 accent-primary"
            />
            Hide bots &amp; conflicts
          </label>
          <fieldset className="m-0 flex gap-[3px] rounded-lg border border-divider p-[3px]">
            <legend className="sr-only">Layout</legend>
            {(
              [
                ["cards", LayoutGrid, "Card view"],
                ["table", Rows3, "Table view"],
              ] as const
            ).map(([value, Icon, name]) => (
              <button
                key={value}
                type="button"
                aria-label={name}
                title={name}
                aria-pressed={layout === value}
                onClick={() => update({ layout: value === "table" ? "table" : undefined })}
                className={cn(
                  "grid h-[32px] w-9 place-items-center rounded-[4px] transition-colors hover:bg-foreground/7 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                  layout === value && "text-primary shadow-[inset_0_0_0_1px_var(--primary)] hover:bg-transparent",
                )}
              >
                <Icon className="size-4" />
              </button>
            ))}
          </fieldset>
        </div>
        <FilterChips />
      </div>

      {query.isPending ? (
        <ResultsSkeleton layout={layout} />
      ) : query.isError ? (
        <div className="rounded-[14px] bg-card elev-sm">
          <EmptyState icon={ServerCrash} title="Something went wrong" error>
            {errorText(query.error)}
          </EmptyState>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-[14px] bg-card elev-sm">
          <EmptyState icon={SearchX} title="No one matches these filters">
            Remove a filter, switch cohort, or try a different name.
          </EmptyState>
        </div>
      ) : layout === "cards" ? (
        <div data-tour="results" className="grid grid-cols-1 gap-4 sm:grid-cols-[repeat(auto-fill,minmax(280px,1fr))]">
          {rows.map((p, i) => (
            <PersonCard key={p.person_id} p={p} index={i} onOpen={() => open(p.person_id)} />
          ))}
        </div>
      ) : (
        <PeopleTable rows={rows} onOpen={open} />
      )}

      {rows.length > 0 && (
        <div className="mt-9 flex flex-col items-center gap-2.5">
          {query.hasNextPage && (
            <Button
              variant="outline"
              size="lg"
              onClick={() => query.fetchNextPage()}
              disabled={query.isFetchingNextPage}
              className="min-w-[180px]"
            >
              {query.isFetchingNextPage ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ChevronDown className="size-4" />
              )}
              {query.isFetchingNextPage ? "Loading…" : `Load ${fmt(Math.min(50, total - rows.length))} more`}
            </Button>
          )}
          <span className="text-xs text-muted-foreground tabular-nums">
            Showing {fmt(rows.length)} of {fmt(total)}
          </span>
        </div>
      )}

      <PersonProfile
        id={search.p}
        ids={navIds}
        onNavigate={(id) => update({ p: id })}
        onClose={() => (takeProfilePushed() ? router.history.back() : update({ p: undefined }))}
      />
    </div>
  );
}

function ResultsSkeleton({ layout }: { layout: "cards" | "table" }) {
  if (layout === "table") return <Skeleton className="h-[420px] rounded-[14px]" />;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-[repeat(auto-fill,minmax(280px,1fr))]">
      {Array.from({ length: 9 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static placeholders
        <div key={i} className="flex flex-col gap-4 rounded-[14px] bg-card p-5 elev-sm">
          <div className="flex gap-3">
            <Skeleton className="size-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3.5 w-3/5" />
              <Skeleton className="h-3 w-2/5" />
            </div>
          </div>
          <Skeleton className="h-2.5" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      ))}
    </div>
  );
}
