import { useRouter } from "@tanstack/react-router";
import { ChevronsDown, Download, LayoutGrid, Loader2, SearchX, ServerCrash, Table2, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
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
import { apiQuery } from "./search";
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

  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="mb-3.5 flex flex-col gap-3">
        <div data-tour="cohorts">
          <CohortSwitcher />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput />
          <div data-tour="filter">
            <FilterMenu />
          </div>
          <div data-tour="sort">
            <SortMenu />
          </div>
          <fieldset className="flex gap-0.5 rounded-[10px] border bg-muted p-[3px]">
            <legend className="sr-only">Layout</legend>
            {(
              [
                ["cards", LayoutGrid, "Card view"],
                ["table", Table2, "Table view"],
              ] as const
            ).map(([value, Icon, name]) => (
              <button
                key={value}
                type="button"
                aria-label={name}
                aria-pressed={layout === value}
                onClick={() => update({ layout: value === "table" ? "table" : undefined })}
                className={cn(
                  "grid h-7 w-8 place-items-center rounded-[7px] text-muted-foreground transition-colors hover:text-foreground",
                  layout === value && "bg-card text-foreground shadow-sm",
                )}
              >
                <Icon className="size-4" />
              </button>
            ))}
          </fieldset>
          <Button data-tour="export" onClick={() => exportDialog.open("filter")} className="gap-2">
            <Download className="size-4" />
            Export
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <FilterChips />
          <div className="flex-1" />
          <label
            htmlFor="hide-flagged"
            className="flex cursor-pointer items-center gap-2 text-[13px] text-muted-foreground select-none"
          >
            <Switch
              id="hide-flagged"
              checked={search.flagged !== "show"}
              onCheckedChange={(on) => update({ flagged: on ? undefined : "show" })}
            />
            Hide bots &amp; conflicts
          </label>
        </div>
      </div>

      <div
        data-testid="result-summary"
        className="mb-3 flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted-foreground"
        aria-live="polite"
      >
        <span>
          {query.isPending ? (
            "Searching…"
          ) : query.isError ? null : (
            <>
              <b className="text-foreground tabular-nums">{fmt(total)}</b>{" "}
              {total === 1 ? "person matches" : "people match"}
            </>
          )}
        </span>
        {search.sort === "commits" && (
          <span className="flex items-center gap-1.5">
            <TriangleAlert className="size-3.5" /> Commit counts include forks and copied history
          </span>
        )}
      </div>

      {query.isPending ? (
        <ResultsSkeleton layout={layout} />
      ) : query.isError ? (
        <div className="rounded-xl border bg-card">
          <EmptyState icon={ServerCrash} title="Something went wrong" error>
            {errorText(query.error)}
          </EmptyState>
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border bg-card">
          <EmptyState icon={SearchX} title="No one matches these filters">
            Remove a filter, switch cohort, or try a different name.
          </EmptyState>
        </div>
      ) : layout === "cards" ? (
        <div data-tour="results" className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(310px,1fr))]">
          {rows.map((p, i) => (
            <PersonCard key={p.person_id} p={p} index={i} onOpen={() => open(p.person_id)} />
          ))}
        </div>
      ) : (
        <PeopleTable rows={rows} onOpen={open} />
      )}

      {query.hasNextPage && (
        <div className="mt-5 flex justify-center">
          <Button
            variant="outline"
            onClick={() => query.fetchNextPage()}
            disabled={query.isFetchingNextPage}
            className="gap-2"
          >
            {query.isFetchingNextPage ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ChevronsDown className="size-4" />
            )}
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
            <span className="text-faint">({fmt(Math.min(50, total - rows.length))})</span>
          </Button>
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
  if (layout === "table") return <Skeleton className="h-[420px] rounded-xl" />;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(310px,1fr))]">
      {Array.from({ length: 9 }, (_, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: static placeholders
        <div key={i} className="flex flex-col gap-3 rounded-xl border bg-card p-4">
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
