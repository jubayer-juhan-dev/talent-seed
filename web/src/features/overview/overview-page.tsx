import { Link } from "@tanstack/react-router";
import {
  Bot,
  ChevronDown,
  ChevronUp,
  Copy,
  Download,
  FlaskConical,
  GitFork,
  Info,
  MailQuestion,
  ServerCrash,
  Star,
  UsersRound,
} from "lucide-react";
import { type ReactNode, useState } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { PersonAvatar } from "@/components/app/person-avatar";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { exportDialog } from "@/features/export/export-store";
import { markProfilePushed } from "@/features/profile/profile-nav";
import { fmt } from "@/lib/format";
import { useShortlist } from "@/lib/shortlist";
import { BarList } from "./bar-list";
import { CohortCards } from "./cohort-cards";
import { TenureHeatmap } from "./tenure-heatmap";

const CHAINS_SHOWN = 12;

function Panel({
  title,
  sub,
  aside,
  children,
  tour,
  className,
}: {
  title: string;
  sub?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  tour?: string;
  className?: string;
}) {
  return (
    <section
      data-tour={tour}
      className={`flex min-w-0 flex-col gap-4 rounded-[14px] bg-card p-5 elev-sm sm:p-7 ${className ?? ""}`}
    >
      <div data-tour={tour && `${tour}-head`} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
        <div>
          <h2 className="text-[17px] font-medium">{title}</h2>
          {sub && <div className="mt-1 text-[13px] text-muted-foreground">{sub}</div>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

const NOTES = [
  [
    FlaskConical,
    "Cohorts are a draft.",
    "P1–P3 follow draft rules that the client hasn't confirmed yet. Each person shows the reason for their cohort.",
  ],
  [MailQuestion, "Emails are unverified", "commit-author addresses. Don't infer an employer from an email domain."],
  [
    GitFork,
    "Commit counts can mislead.",
    "Forks and copied history inflate them, so results sort by days active in the last 84 days.",
  ],
  [
    Bot,
    "Some automation accounts remain.",
    "Known bots and GitHub conflicts are hidden by default, but a few (e.g. price updaters) slip through.",
  ],
  [Copy, "One person can appear twice", "when their developer ids share no GitHub account."],
] as const;

const rowLink =
  "-mx-2.5 grid items-center gap-3 rounded-lg p-2.5 text-foreground transition-colors hover:bg-foreground/5 focus-visible:bg-foreground/5 focus-visible:outline-2 focus-visible:outline-ring";

/** The five most active P1 people, as on Explore's default view. */
function MostActive() {
  const { data, isPending } = $api.useQuery(
    "get",
    "/api/people",
    // `page` keeps this cache entry apart from Explore's infinite query, which has the same filters but stores pages
    { params: { query: { page: 1, cohort: "P1", hide_flagged: "1", sort: "active_days", dir: "desc" } } },
    { staleTime: 5 * 60_000 },
  );
  const rows = data?.rows.slice(0, 5) ?? [];
  return (
    <Panel
      title="Most active this period"
      aside={
        <Link to="/explore" className="text-[13px] text-primary hover:text-brand-400">
          View all
        </Link>
      }
      className="gap-3"
    >
      <div className="flex flex-col">
        {isPending && [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="my-1.5 h-10 rounded-lg" />)}
        {rows.map((p) => (
          <Link
            key={p.person_id}
            to="/explore"
            search={{ p: p.person_id }}
            onClick={markProfilePushed}
            className={`${rowLink} grid-cols-[32px_minmax(0,1fr)_auto]`}
          >
            <PersonAvatar person={p} className="size-8 text-[13px]" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">
                {p.display_name || p.github_login || "(no name)"}
              </span>
              <span className="block truncate text-xs text-muted-foreground">
                {(p.top_level_ecosystems ?? []).slice(0, 3).join(", ") || "No chain"}
              </span>
            </span>
            <span className="text-[13px] text-muted-foreground tabular-nums">{fmt(p.active_days_in_window)} days</span>
          </Link>
        ))}
      </div>
    </Panel>
  );
}

function JobsPanel() {
  const { data, isPending } = $api.useQuery("get", "/api/jobs", {}, { staleTime: 60_000 });
  const jobs = data?.slice(0, 3) ?? [];
  return (
    <Panel
      title="Jobs"
      aside={
        <Link to="/jobs" className="text-[13px] text-primary hover:text-brand-400">
          Open jobs
        </Link>
      }
      className="gap-3"
    >
      <div className="flex flex-col">
        {isPending && [0, 1, 2].map((i) => <Skeleton key={i} className="my-1.5 h-10 rounded-lg" />)}
        {!isPending && jobs.length === 0 && (
          <p className="text-[13px] text-muted-foreground">
            No jobs yet.{" "}
            <Link to="/jobs" className="text-primary hover:text-brand-400">
              Paste a posting
            </Link>{" "}
            to rank talents against it.
          </p>
        )}
        {jobs.map((j) => (
          <Link
            key={j.job_id}
            to="/jobs/$jobId"
            params={{ jobId: j.job_id }}
            className={`${rowLink} grid-cols-[minmax(0,1fr)_auto]`}
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{j.title}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {[j.company, j.location_text || j.location_country].filter(Boolean).join(" · ") || "—"}
              </span>
            </span>
            <span className="text-[13px] text-brand-300 tabular-nums">{fmt(j.matches_count)}</span>
          </Link>
        ))}
      </div>
    </Panel>
  );
}

function ShortlistPanel() {
  const list = useShortlist();
  return (
    <Panel
      title="Shortlist"
      aside={
        <span className="text-xs text-muted-foreground">
          {list.length} {list.length === 1 ? "person" : "people"}
        </span>
      }
      className="gap-3.5"
    >
      {list.length ? (
        <div className="flex items-center">
          {list.slice(0, 8).map((p) => (
            <span key={p.person_id} title={p.display_name ?? p.github_login ?? p.person_id} className="-mr-2">
              <PersonAvatar person={p} className="size-9 border-2 border-card text-[13px]" />
            </span>
          ))}
          {list.length > 8 && <span className="ml-4 text-xs text-muted-foreground">+{list.length - 8}</span>}
        </div>
      ) : (
        <p className="flex items-center gap-2 text-[13px] text-muted-foreground">
          <Star className="size-4 text-primary" />
          Star people in Explore to collect them here.
        </p>
      )}
      <Button
        variant="outline"
        className="self-start"
        disabled={!list.length}
        onClick={() => exportDialog.open("shortlist")}
      >
        <Download /> Export shortlist
      </Button>
    </Panel>
  );
}

export function OverviewPage() {
  const { data, error } = $api.useQuery("get", "/api/overview", {}, { staleTime: 5 * 60_000 });
  const counts = data && Object.fromEntries(data.cohorts.map((c) => [c.k, c.n]));
  const [noCountry, active] = data?.no_country ?? [0, 0];
  const [allChains, setAllChains] = useState(false);
  const [notesOpen, setNotesOpen] = useState(false);
  const chains = data ? (allChains ? data.chains : data.chains.slice(0, CHAINS_SHOWN)) : [];

  return (
    <div className="flex animate-in flex-col gap-6 duration-300 fade-in slide-in-from-bottom-1">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-[640px]">
          <h1 className="mb-2.5 text-3xl font-medium tracking-[-0.025em] sm:text-[40px] sm:leading-[1.1]">
            Crypto developer talent
          </h1>
          <p className="text-[15px] leading-relaxed text-pretty text-muted-foreground">
            The most active open-source crypto developers, by chain and cohort. Click any card, bar or cell to see the
            people behind it.
          </p>
        </div>
        <Button asChild size="lg">
          <Link to="/explore">
            <UsersRound /> Explore all talent
          </Link>
        </Button>
      </header>

      {error ? (
        <div className="rounded-[14px] bg-card elev-sm">
          <EmptyState icon={ServerCrash} title="Couldn't load the overview" error>
            {errorText(error)}
          </EmptyState>
        </div>
      ) : (
        <>
          <CohortCards counts={counts} />
          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
            <Panel
              title="Active developers per chain"
              sub={data ? `Top ${chains.length} of ${data.chains.length} chains` : "Loading…"}
              tour="chains"
              aside={
                <div className="flex gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <i className="size-2.5 rounded-[3px] bg-p1-mark" />
                    P1
                  </span>
                  <span className="flex items-center gap-1.5">
                    <i className="size-2.5 rounded-[3px] bg-brand-700" />
                    P2–P3
                  </span>
                </div>
              }
            >
              {data ? (
                <>
                  <BarList
                    bars={chains.map((c) => ({
                      key: c.k,
                      label: c.k,
                      total: c.n,
                      segments: [
                        { value: c.p1, className: "bg-p1-mark" },
                        { value: c.n - c.p1, className: "bg-brand-700" },
                      ],
                      tip: (
                        <>
                          <b>{c.k}</b>
                          <br />
                          {fmt(c.n)} active developers
                          <br />
                          {fmt(c.p1)} in P1 · {fmt(c.n - c.p1)} in P2–P3
                        </>
                      ),
                      search: { cohort: "P1,P2,P3", eco: c.k },
                    }))}
                  />
                  {data.chains.length > CHAINS_SHOWN && (
                    <Button
                      variant="accent"
                      size="sm"
                      className="-ml-2 self-start"
                      aria-expanded={allChains}
                      onClick={() => setAllChains((v) => !v)}
                    >
                      {allChains ? <ChevronUp /> : <ChevronDown />}
                      {allChains ? `Show top ${CHAINS_SHOWN}` : `Show all ${data.chains.length} chains`}
                    </Button>
                  )}
                </>
              ) : (
                <Skeleton className="h-[440px]" />
              )}
            </Panel>
            <div className="flex min-w-0 flex-col gap-6">
              <Panel title="Tenure × activity" sub="P1–P3 people. Brighter cells hold more people." tour="heatmap">
                {data ? <TenureHeatmap mix={data.mix} /> : <Skeleton className="h-[230px]" />}
              </Panel>
              <Panel
                title="Top countries"
                aside={
                  active > 0 && (
                    <span className="text-xs text-muted-foreground">
                      {Math.round((noCountry / active) * 100)}% have no country
                    </span>
                  )
                }
              >
                {data ? (
                  <BarList
                    variant="track"
                    bars={data.countries.map((c) => ({
                      key: c.k,
                      label: c.k,
                      total: c.n,
                      segments: [{ value: c.n, className: "bg-brand-500" }],
                      tip: (
                        <>
                          <b>{c.k}</b>
                          <br />
                          {fmt(c.n)} active developers
                        </>
                      ),
                      search: { cohort: "P1,P2,P3", country: c.k },
                    }))}
                  />
                ) : (
                  <Skeleton className="h-[260px]" />
                )}
              </Panel>
            </div>
          </div>

          <div className="grid grid-cols-1 items-start gap-6 md:grid-cols-2 xl:grid-cols-3">
            <MostActive />
            <JobsPanel />
            <ShortlistPanel />
          </div>
        </>
      )}

      <section className="rounded-[14px] border border-divider px-5 py-5 sm:px-7 sm:py-6">
        <button
          type="button"
          aria-expanded={notesOpen}
          onClick={() => setNotesOpen((v) => !v)}
          className="flex w-full items-center justify-between gap-3 rounded-md py-1 text-left text-[15px] font-medium focus-visible:outline-2 focus-visible:outline-ring"
        >
          <span className="flex items-center gap-2.5">
            <Info className="size-4 text-primary" />
            How to read this data
          </span>
          {notesOpen ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
        </button>
        {notesOpen && (
          <ul className="mt-5 grid animate-in grid-cols-1 gap-x-8 gap-y-5 fade-in md:grid-cols-2">
            {NOTES.map(([Icon, bold, rest]) => (
              <li key={bold} className="grid grid-cols-[20px_minmax(0,1fr)] gap-3 text-[13px] leading-relaxed">
                <Icon className="mt-0.5 size-4 text-muted-foreground" />
                <span>
                  <span className="font-medium">{bold}</span> <span className="text-muted-foreground">{rest}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
