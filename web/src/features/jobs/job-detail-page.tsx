import { useQueryClient } from "@tanstack/react-query";
import { getRouteApi, Link, useRouter } from "@tanstack/react-router";
import {
  ArrowDown,
  ArrowLeft,
  Briefcase,
  Building2,
  ChevronDown,
  ChevronUp,
  Loader2,
  MapPin,
  Pencil,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { $api, fetchClient, type Schemas } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { PersonAvatar } from "@/components/app/person-avatar";
import { StarButton } from "@/components/app/star-button";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PersonProfile } from "@/features/profile/person-profile";
import { markProfilePushed, takeProfilePushed } from "@/features/profile/profile-nav";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { CoverageIcon, CoverageLegend, coverageLabel } from "./coverage";
import { jobPlace } from "./jobs-page";
import { type JobRequirement, RequirementGroups, RequirementsEditor } from "./requirements";

type MatchRow = Schemas["MatchRow"];
type MatchConcept = Schemas["MatchConcept"];

const route = getRouteApi("/jobs/$jobId");

const PAGE = 50;

const FILTERS = [
  { id: "all", label: "All", hint: "Everyone with evidence for at least one requirement" },
  { id: "required", label: "Required covered", hint: "No required skill missing (covered or partial)" },
  { id: "contributors", label: "Contributors", hint: "Has contributor-level code evidence for a requirement" },
] as const;
type Filter = (typeof FILTERS)[number]["id"];

const passes = (m: MatchRow, f: Filter) =>
  f === "all" ||
  (f === "contributors"
    ? m.contributor_concepts > 0
    : m.breakdown.every((b) => b.requirement !== "required" || b.state !== "missing"));

/** Tooltip text for one requirement cell: what the evidence is, not just its colour. */
function cellTitle(b: MatchConcept) {
  if (b.state === "unscored") return "Not scored · no talent has evidence for this yet";
  const parts = [`${coverageLabel(b.state)} · ${b.requirement === "required" ? "required" : "nice to have"}`];
  if (b.evidence_status) {
    let ev = b.evidence_status;
    if (b.usage_level) ev += ` · ${b.usage_level.replace("_USAGE", "").toLowerCase()}`;
    if (b.evidence_status === "INFERENCE" && b.confidence != null) ev += ` (${Math.round(b.confidence * 100)}%)`;
    parts.push(ev);
  } else parts.push("no evidence");
  return parts.join("\n");
}

function MatchCard({ m, rank, onOpen }: { m: MatchRow; rank: number; onOpen: (id: string) => void }) {
  const pct = Math.round(m.score * 100);
  // required first, then nice-to-have — the same order as the requirements card
  const cells = [...m.breakdown].sort(
    (a, b) => Number(a.requirement !== "required") - Number(b.requirement !== "required"),
  );
  return (
    <div className="grid grid-cols-[28px_minmax(0,1fr)_36px] items-center gap-x-4 gap-y-3 rounded-[14px] bg-card px-4 py-4 elev-sm transition-shadow hover:elev-md sm:px-6 sm:py-5 lg:grid-cols-[36px_minmax(200px,1fr)_minmax(0,2.4fr)_170px_40px] lg:gap-5">
      <div className="text-[13px] text-muted-foreground tabular-nums">{String(rank).padStart(2, "0")}</div>
      <div className="flex min-w-0 items-center gap-3">
        <PersonAvatar
          person={{ display_name: m.name ?? m.github_login, github_user_id: m.github_user_id }}
          className="size-[38px]"
        />
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => onOpen(m.talent_id)}
            className="block max-w-full truncate text-left text-[15px] font-medium transition-colors hover:text-primary"
          >
            {m.name ?? m.github_login ?? m.talent_id}
          </button>
          <div className="mt-0.5 flex items-center gap-2 text-xs">
            {m.github_login && <span className="truncate text-muted-foreground">@{m.github_login}</span>}
            {m.contributor_concepts > 0 && (
              <span
                className="rounded-md bg-brand-800 px-1.5 py-px text-[10px] whitespace-nowrap text-brand-100"
                title="Requirements backed by contributor-level code evidence"
              >
                Contributor ×{m.contributor_concepts}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="col-span-3 flex flex-wrap gap-1.5 lg:col-span-1">
        {cells.map((b) => (
          <span
            key={`${b.concept_id}-${b.requirement}`}
            title={cellTitle(b)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full bg-background px-2.5 py-1 text-xs",
              b.requirement !== "required" && "ring-1 ring-border ring-inset",
              (b.state === "missing" || b.state === "unscored") && "text-faint",
              b.state === "unscored" && "line-through decoration-faint/60",
            )}
          >
            <CoverageIcon state={b.state} />
            {b.concept_name}
          </span>
        ))}
      </div>
      <div className="col-span-3 flex items-center gap-3 lg:col-span-1">
        <span className="h-1 flex-1 overflow-hidden rounded-sm bg-neutral-800">
          <span
            className="block h-full origin-left animate-grow-x rounded-sm bg-primary shadow-[0_0_8px_var(--primary)]"
            style={{ width: `${pct}%` }}
          />
        </span>
        <span className="w-11 text-right text-lg font-medium tabular-nums">{pct}%</span>
      </div>
      <StarButton
        className="col-start-3 row-start-1 size-9 lg:col-start-5"
        person={{
          person_id: m.talent_id,
          display_name: m.name,
          github_login: m.github_login,
          github_user_id: m.github_user_id,
          priority_cohort: m.priority_cohort,
          country: m.country,
        }}
      />
    </div>
  );
}

function useMatches(jobId: string) {
  return $api.useInfiniteQuery(
    "get",
    "/api/jobs/{job_id}/matches",
    { params: { path: { job_id: jobId }, query: { limit: PAGE } } },
    {
      pageParamName: "offset",
      initialPageParam: 0,
      getNextPageParam: (last) =>
        last.offset + last.items.length < last.total ? last.offset + last.items.length : undefined,
      staleTime: 60_000,
    },
  );
}

function Matches({ query, onOpen }: { query: ReturnType<typeof useMatches>; onOpen: (id: string) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const all = query.data?.pages.flatMap((p) => p.items) ?? [];
  const total = query.data?.pages[0]?.total ?? 0;
  const ranked = all.map((m, i) => ({ m, rank: i + 1 })).filter(({ m }) => passes(m, filter));

  return (
    <section className="mt-14">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-5">
        <div>
          <h2 className="mb-1.5 text-2xl font-medium">Matches</h2>
          <p className="text-[13px] text-muted-foreground">
            {query.isLoading
              ? "Ranking talents…"
              : filter === "all"
                ? `Showing top ${fmt(all.length)} of ${fmt(total)}, ranked by weighted coverage of the requirements`
                : `${fmt(ranked.length)} filtered from top ${fmt(all.length)}`}
          </p>
        </div>
        <fieldset
          aria-label="Filter matches"
          className="m-0 inline-flex min-w-0 gap-[3px] rounded-lg border border-divider p-[3px]"
        >
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              title={f.hint}
              onClick={() => setFilter(f.id)}
              className={cn(
                "rounded-[4px] px-3.5 py-1.5 text-[13px] transition-colors hover:bg-foreground/7",
                filter === f.id && "text-primary shadow-[inset_0_0_0_1px_var(--primary)] hover:bg-transparent",
              )}
            >
              {f.label}
            </button>
          ))}
        </fieldset>
      </div>

      <div className="flex flex-col gap-3">
        {query.isLoading && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[78px] rounded-[14px]" />)}
        {ranked.map(({ m, rank }) => (
          <MatchCard key={m.talent_id} m={m} rank={rank} onOpen={onOpen} />
        ))}
      </div>
      {query.isError && (
        <EmptyState icon={Briefcase} title="Couldn't load matches" error>
          Try reloading the page.
        </EmptyState>
      )}
      {query.isSuccess && total === 0 && (
        <EmptyState icon={Briefcase} title="No matches yet">
          No talent has evidence for these requirements.
        </EmptyState>
      )}
      {query.isSuccess && total > 0 && ranked.length === 0 && (
        <p className="py-6 text-sm text-muted-foreground">
          None of the loaded talents pass this filter. Load more, or switch back to All.
        </p>
      )}

      {total > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-4">
          {query.hasNextPage && (
            <Button size="lg" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
              {query.isFetchingNextPage ? <Loader2 className="animate-spin" /> : <ArrowDown />}
              {query.isFetchingNextPage ? "Loading…" : `Load ${Math.min(PAGE, total - all.length)} more`}
            </Button>
          )}
          <span className="text-[13px] text-muted-foreground tabular-nums">
            {fmt(all.length)} of {fmt(total)} loaded
          </span>
        </div>
      )}
      <CoverageLegend className="mt-5" />
    </section>
  );
}

/** The job's requirement set, with an edit mode that saves through the recruiter-correction endpoint.
 *  Saving re-ranks the matches (all job queries are refetched). */
function RequirementsPanel({ jobId, requirements }: { jobId: string; requirements: JobRequirement[] }) {
  const [draft, setDraft] = useState<JobRequirement[] | null>(null);
  const [saving, setSaving] = useState(false);
  const queryClient = useQueryClient();

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    const res = await fetchClient.PATCH("/api/jobs/{job_id}/requirements", {
      params: { path: { job_id: jobId } },
      body: draft.map((r) => ({
        concept_id: r.concept_id ?? undefined,
        concept_name: r.concept_name,
        concept_type: r.concept_type,
        requirement: r.requirement,
      })),
    });
    setSaving(false);
    if (res.error) {
      toast.error("Couldn't save the requirements");
      return;
    }
    setDraft(null);
    toast("Requirements saved — matches re-ranked");
    queryClient.invalidateQueries();
  };

  if (!draft)
    return (
      <div className="relative">
        <Button variant="accent" size="sm" className="absolute -top-1 right-0" onClick={() => setDraft(requirements)}>
          <Pencil /> Edit
        </Button>
        <RequirementGroups requirements={requirements} />
      </div>
    );

  return (
    <div className="space-y-4">
      <div>
        <div className="text-sm font-medium">Edit requirements</div>
        <p className="text-xs text-muted-foreground">
          Pick from the Talent Ontology, and set each one as required or nice to have. Matches re-rank when you save.
        </p>
      </div>
      <RequirementsEditor value={draft} onChange={setDraft} />
      <div className="flex justify-end gap-2.5">
        <Button variant="outline" onClick={() => setDraft(null)} disabled={saving}>
          Cancel
        </Button>
        <Button onClick={save} disabled={saving || draft.length === 0}>
          {saving && <Loader2 className="animate-spin" />}
          {saving ? "Saving…" : "Save requirements"}
        </Button>
      </div>
    </div>
  );
}

export function JobDetailPage({ jobId }: { jobId: string }) {
  const job = $api.useQuery("get", "/api/jobs/{job_id}", { params: { path: { job_id: jobId } } });
  const matches = useMatches(jobId);
  const first = matches.data?.pages[0];
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const router = useRouter();
  const setProfile = (p: string | undefined, push = false) =>
    navigate({ search: (prev) => ({ ...prev, p }), replace: !push });
  const openProfile = (id: string) => {
    markProfilePushed();
    setProfile(id, true);
  };
  // ←/→ in the profile step through the loaded matches, in rank order
  const ids = matches.data?.pages.flatMap((pg) => pg.items.map((m) => m.talent_id)) ?? [];
  const [descOpen, setDescOpen] = useState(false);
  const j = job.data;
  const place = j ? jobPlace(j) : null;

  return (
    <div>
      <Button asChild variant="accent" className="-ml-2 px-2">
        <Link to="/jobs">
          <ArrowLeft /> All jobs
        </Link>
      </Button>

      {job.isLoading && <Skeleton className="mt-7 h-64 w-full rounded-[14px]" />}
      {job.isError && (
        <EmptyState icon={Briefcase} title="Job not found" error>
          It may have been removed. Go back to all jobs.
        </EmptyState>
      )}

      {j && (
        <>
          <header className="mt-7 mb-10 flex flex-wrap items-end justify-between gap-x-10 gap-y-6">
            <div className="max-w-[640px]">
              <div className="mb-3.5 flex flex-wrap gap-2">
                <span className="rounded-md border border-primary px-2.5 py-[3px] text-[11px] tracking-wide text-primary capitalize">
                  {j.source}
                </span>
                {j.remote && (
                  <span className="rounded-md bg-neutral-800 px-2.5 py-[3px] text-[11px] tracking-wide text-neutral-100">
                    Remote
                  </span>
                )}
                {j.posted_at && (
                  <span className="rounded-md bg-neutral-800 px-2.5 py-[3px] text-[11px] tracking-wide text-neutral-100">
                    Posted {j.posted_at}
                  </span>
                )}
              </div>
              <h1 className="mb-2.5 text-3xl font-medium tracking-[-0.025em] text-pretty sm:text-[40px] sm:leading-[1.1]">
                {j.title}
              </h1>
              <div className="flex flex-wrap gap-4 text-[15px] text-muted-foreground">
                {j.company && (
                  <span className="flex items-center gap-1.5">
                    <Building2 className="size-4" />
                    {j.company}
                  </span>
                )}
                {place && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="size-4" />
                    {place}
                  </span>
                )}
              </div>
            </div>
            <div className="flex gap-10">
              <div>
                <div className="text-[32px] font-medium tracking-tight text-brand-300 tabular-nums">
                  {first ? fmt(first.total) : "–"}
                </div>
                <div className="text-xs text-muted-foreground">talents matched</div>
              </div>
              <div>
                <div className="text-[32px] font-medium tracking-tight tabular-nums">
                  {first ? fmt(first.pool) : "–"}
                </div>
                <div className="text-xs text-muted-foreground">with evidence</div>
              </div>
            </div>
          </header>

          <section className="flex flex-col gap-6 rounded-[14px] bg-card p-5 elev-sm sm:p-7">
            <RequirementsPanel jobId={jobId} requirements={j.requirements} />
            <div className="hr-fade" />
            <div>
              <Button
                variant="accent"
                size="sm"
                className="-ml-1.5"
                aria-expanded={descOpen}
                onClick={() => setDescOpen((v) => !v)}
              >
                {descOpen ? <ChevronUp /> : <ChevronDown />}
                {descOpen ? "Hide full description" : "Show full description"}
              </Button>
              {descOpen && (
                <p className="mt-3 max-w-[68ch] text-sm leading-relaxed whitespace-pre-line text-pretty text-muted-foreground">
                  {j.description}
                </p>
              )}
            </div>
          </section>

          <Matches query={matches} onOpen={openProfile} />
          <PersonProfile
            id={search.p}
            ids={ids}
            onNavigate={(id) => setProfile(id)}
            onClose={() => (takeProfilePushed() ? router.history.back() : setProfile(undefined))}
          />
        </>
      )}
    </div>
  );
}
