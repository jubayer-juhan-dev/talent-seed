import {
  Blocks,
  Bot,
  Copy,
  FlaskConical,
  GitFork,
  Globe,
  Grid3x3,
  Info,
  MailQuestion,
  ServerCrash,
} from "lucide-react";
import type { ReactNode } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { fmt } from "@/lib/format";
import { BarList } from "./bar-list";
import { CohortCards } from "./cohort-cards";
import { TenureHeatmap } from "./tenure-heatmap";

function Panel({
  icon,
  title,
  aside,
  children,
  tour,
}: {
  icon: ReactNode;
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  tour?: string;
}) {
  return (
    <section data-tour={tour} className="rounded-xl border bg-card shadow-xs">
      <div data-tour={tour && `${tour}-head`} className="flex items-center justify-between gap-2.5 px-[18px] pt-4">
        <h2 className="flex items-center gap-2 text-[14.5px] font-semibold [&_svg]:size-4 [&_svg]:text-muted-foreground">
          {icon}
          {title}
        </h2>
        {aside}
      </div>
      <div className="px-[18px] pt-3.5 pb-[18px]">{children}</div>
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

export function OverviewPage() {
  const { data, error } = $api.useQuery("get", "/api/overview", {}, { staleTime: 5 * 60_000 });
  const counts = data && Object.fromEntries(data.cohorts.map((c) => [c.k, c.n]));
  const [noCountry, active] = data?.no_country ?? [0, 0];

  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
      <h1 className="text-2xl font-bold tracking-tight">Crypto developer talent</h1>
      <p className="mt-1 mb-5 max-w-3xl text-muted-foreground">
        Who the most active open-source crypto developers are, by chain and cohort. Click a card, bar or cell to see the
        people behind it.
      </p>
      {error ? (
        <div className="rounded-xl border bg-card">
          <EmptyState icon={ServerCrash} title="Couldn't load the overview" error>
            {errorText(error)}
          </EmptyState>
        </div>
      ) : (
        <>
          <CohortCards counts={counts} />
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <Panel
              icon={<Blocks />}
              title="Active developers per chain"
              tour="chains"
              aside={
                <div className="flex gap-3.5 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <i className="size-2.5 rounded-[3px] bg-bar-strong" />
                    P1
                  </span>
                  <span className="flex items-center gap-1.5">
                    <i className="size-2.5 rounded-[3px] bg-bar-light" />
                    P2–P3
                  </span>
                </div>
              }
            >
              {data ? (
                <BarList
                  bars={data.chains.map((c) => ({
                    key: c.k,
                    label: c.k,
                    total: c.n,
                    segments: [
                      { value: c.p1, className: "bg-bar-strong" },
                      { value: c.n - c.p1, className: "bg-bar-light" },
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
              ) : (
                <Skeleton className="h-[600px]" />
              )}
            </Panel>
            <div className="flex min-w-0 flex-col gap-4">
              <Panel
                icon={<Grid3x3 />}
                title="Tenure × activity"
                tour="heatmap"
                aside={<span className="text-xs text-faint">P1–P3 people</span>}
              >
                {data ? <TenureHeatmap mix={data.mix} /> : <Skeleton className="h-[220px]" />}
              </Panel>
              <Panel
                icon={<Globe />}
                title="Top countries"
                aside={
                  active > 0 && (
                    <span className="text-xs text-faint">
                      {Math.round((noCountry / active) * 100)}% have no country
                    </span>
                  )
                }
              >
                {data ? (
                  <BarList
                    bars={data.countries.map((c) => ({
                      key: c.k,
                      label: c.k,
                      total: c.n,
                      segments: [{ value: c.n, className: "bg-bar-strong" }],
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
                  <Skeleton className="h-[300px]" />
                )}
              </Panel>
            </div>
          </div>
        </>
      )}
      <div className="mt-4">
        <Panel icon={<Info />} title="How to read this data">
          <ul className="flex flex-col gap-3 text-[13px]">
            {NOTES.map(([Icon, bold, rest]) => (
              <li key={bold} className="flex items-start gap-2.5">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <span className="text-muted-foreground">
                  <b className="font-semibold text-foreground">{bold}</b> {rest}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
