import {
  Activity,
  Blocks,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Clock,
  Copy,
  FolderX,
  GitFork,
  Hexagon,
  Hourglass,
  Lightbulb,
  MailQuestion,
  MailX,
  MapPin,
  ShieldCheck,
  Star,
  TriangleAlert,
  Users,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { toast } from "sonner";
import type { PersonDetail } from "@/api/client";
import { $api } from "@/api/client";
import { AiBadge } from "@/components/app/ai-badge";
import { CohortBadge } from "@/components/app/cohort-badge";
import { EmptyState } from "@/components/app/empty-state";
import { GithubIcon } from "@/components/app/github-icon";
import { PersonAvatar } from "@/components/app/person-avatar";
import { StarButton } from "@/components/app/star-button";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { FLAG_INFO } from "@/features/explore/person-tags";
import { day, fmt, label } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ComponentsSection, EnrichmentSection } from "./enrichment-section";
import { GithubProfileSection } from "./github-profile-section";

type Props = {
  d: PersonDetail;
  prev?: string;
  next?: string;
  /** "3 of 50": where this person sits in the list ←/→ step through */
  pos?: string;
  onNavigate: (id: string) => void;
  onClose: () => void;
};

const CALLOUT: Record<string, string> = {
  P1: "bg-p1-soft text-p1",
  P2: "bg-p2-soft text-p2",
  P3: "bg-p3-soft text-p3",
  HOLD: "bg-hold-soft text-hold",
};
const CALLOUT_BORDER: Record<string, string> = {
  P1: "border-[color-mix(in_srgb,var(--p1-mark)_35%,transparent)]",
  P2: "border-[color-mix(in_srgb,var(--p2-mark)_35%,transparent)]",
  P3: "border-[color-mix(in_srgb,var(--p3-mark)_35%,transparent)]",
  HOLD: "border-[color-mix(in_srgb,var(--hold-mark)_35%,transparent)]",
};

function Tip({ tip, children }: { tip: ReactNode; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>{children}</TooltipTrigger>
      <TooltipContent className="max-w-64">{tip}</TooltipContent>
    </Tooltip>
  );
}

function IconButton({
  label: name,
  tip,
  ...rest
}: { label: string; tip: string } & React.ComponentProps<typeof Button>) {
  return (
    <Tip tip={tip}>
      <Button variant="ghost" size="icon" aria-label={name} {...rest} />
    </Tip>
  );
}

export function ProfileBody({ d, prev, next, pos, onNavigate, onClose }: Props) {
  const p = d.person;
  const enr = $api.useQuery("get", "/api/person/enrichment", {
    params: { query: { id: p.person_id } },
  });
  const aiLocation = enr.data?.location ?? null;
  const tops = d.ecosystems.filter((e) => e.level === "TOP_LEVEL");
  const subs = d.ecosystems.filter((e) => e.level !== "TOP_LEVEL");
  const apiLogin = (p.github_login_source ?? "").startsWith("GITHUB_API_");

  return (
    <div className="flex min-h-0 flex-1 flex-col animate-in fade-in duration-200">
      {/* header */}
      <div className="flex shrink-0 flex-col gap-5 px-5 pt-5 sm:px-7 sm:pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1">
            <IconButton
              label="Previous person"
              tip="Previous (←)"
              disabled={!prev}
              onClick={() => prev && onNavigate(prev)}
            >
              <ChevronUp className="size-4" />
            </IconButton>
            <IconButton label="Next person" tip="Next (→)" disabled={!next} onClick={() => next && onNavigate(next)}>
              <ChevronDown className="size-4" />
            </IconButton>
            {pos && <span className="ml-1.5 text-xs text-muted-foreground tabular-nums">{pos}</span>}
          </div>
          <div className="flex items-center gap-1">
            <StarButton person={p} />
            <IconButton label="Close" tip="Close (Esc)" onClick={onClose}>
              <X className="size-[17px]" />
            </IconButton>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <PersonAvatar person={p} className="size-14 text-[22px]" />
          <div className="min-w-0">
            <h2 className="flex flex-wrap items-center gap-2 text-[22px] font-medium tracking-[-0.01em]">
              {p.display_name || "(no name)"} <CohortBadge cohort={p.priority_cohort} /> <AiBadge person={p} />
            </h2>
            <div className="mt-1 flex flex-wrap gap-x-3.5 gap-y-1.5 text-[13px] text-muted-foreground [&_svg]:size-3.5">
              {p.github_login ? (
                <Tip
                  tip={
                    apiLogin
                      ? `Login looked up via the GitHub API on ${day(p.github_login_looked_up_at)}`
                      : "Open GitHub profile"
                  }
                >
                  <a
                    href={`https://github.com/${encodeURIComponent(p.github_login)}`}
                    target="_blank"
                    rel="noopener"
                    className="inline-flex items-center gap-1 text-primary hover:text-brand-400"
                  >
                    <GithubIcon />
                    {p.github_login}
                  </a>
                </Tip>
              ) : p.github_user_id != null ? (
                <Tip tip={`GitHub account id ${p.github_user_id} is known, but its login hasn't been looked up yet.`}>
                  <span className="inline-flex items-center gap-1">
                    <GithubIcon />
                    Login not looked up yet
                  </span>
                </Tip>
              ) : (
                <span className="inline-flex items-center gap-1">
                  <GithubIcon />
                  No GitHub match
                </span>
              )}
              <span className="inline-flex items-center gap-1">
                <MapPin />
                {p.location || p.country || aiLocation || "Location unknown"}
              </span>
              <Tip tip="How sure we are this is the right GitHub account">
                <span className="inline-flex items-center gap-1">
                  <ShieldCheck />
                  Identity match: {label(p.github_confidence)}
                </span>
              </Tip>
            </div>
          </div>
        </div>
      </div>

      <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col gap-0">
        <div className="mx-5 mt-5 shrink-0 overflow-x-auto border-b border-divider sm:mx-7">
          <TabsList variant="line" className="h-11 gap-1 p-0">
            <TabsTrigger value="overview" className={tabClass}>
              Overview
            </TabsTrigger>
            <TabsTrigger value="contact" className={tabClass}>
              Contact <span className="text-xs text-muted-foreground">{d.contacts.length}</span>
            </TabsTrigger>
            <TabsTrigger value="repos" className={tabClass}>
              Repos <span className="text-xs text-muted-foreground">{fmt(d.repo_total)}</span>
            </TabsTrigger>
            <TabsTrigger value="details" className={tabClass}>
              Data details
            </TabsTrigger>
          </TabsList>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <TabsContent value="overview" className="flex flex-col gap-7 px-5 pt-6 pb-10 sm:px-7">
            <Overview d={d} tops={tops} subs={subs} />
          </TabsContent>
          <TabsContent value="contact" className="flex flex-col gap-5 px-5 pt-6 pb-10 sm:px-7">
            <Contact d={d} />
          </TabsContent>
          <TabsContent value="repos" className="flex flex-col gap-3 px-5 pt-6 pb-10 sm:px-7">
            <Repos d={d} />
          </TabsContent>
          <TabsContent value="details" className="flex flex-col gap-5 px-5 pt-6 pb-10 sm:px-7">
            <Details d={d} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

function Callout({
  icon,
  title,
  children,
  className,
  iconClass,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  className?: string;
  iconClass?: string;
}) {
  return (
    <div className={cn("grid grid-cols-[32px_minmax(0,1fr)] gap-3 rounded-lg border border-divider p-4", className)}>
      <div className={cn("grid size-8 shrink-0 place-items-center rounded-lg [&_svg]:size-4", iconClass)}>{icon}</div>
      <div className="min-w-0 text-[13px]">
        <h4 className="mb-0.5 text-sm font-medium text-foreground">{title}</h4>
        {children}
      </div>
    </div>
  );
}

function Stat({
  icon,
  k,
  v,
  s,
  children,
}: {
  icon: ReactNode;
  k: string;
  v: ReactNode;
  s: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-lg bg-background p-4">
      <span className="flex items-center gap-1.5 text-xs text-muted-foreground [&_svg]:size-3.5">
        {icon}
        {k}
      </span>
      <span className="mt-0.5 text-2xl font-medium tracking-[-0.02em] tabular-nums">{v}</span>
      {children}
      <span className="text-xs text-muted-foreground">{s}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2.5 text-[15px] font-medium">{title}</h3>
      {children}
    </section>
  );
}

const capitalize = (t: string | null | undefined) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : "");

const tagClass =
  "inline-flex items-center gap-1.5 rounded-full bg-background px-2.5 py-[5px] text-xs whitespace-nowrap";
const tabClass =
  "h-full flex-none rounded-none px-3 font-medium after:bottom-[-1px]! after:bg-primary! data-active:bg-transparent! data-active:text-foreground";

function Overview({
  d,
  tops,
  subs,
}: {
  d: PersonDetail;
  tops: PersonDetail["ecosystems"];
  subs: PersonDetail["ecosystems"];
}) {
  const p = d.person;
  const flags = (Object.keys(FLAG_INFO) as (keyof typeof FLAG_INFO)[]).filter((f) => p[`flag_${f}`]);
  const years = p.tenure_days != null ? (p.tenure_days / 365.25).toFixed(1) : null;
  const window = p.activity_window_start ?? "";
  const ecoTip = (e: PersonDetail["ecosystems"][number]) =>
    `${e.repo_count} repos · ${fmt(e.commits)} commits · last active ${day(e.last_active_date)}`;
  return (
    <>
      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2">
        <Stat
          icon={<Activity />}
          k="Active days, last 84"
          v={fmt(p.active_days_in_window)}
          s={`${label(p.activity_segment)} · max ${fmt(p.max_active_days_in_28d)} in 28 days`}
        >
          <div className="my-1 h-1 overflow-hidden rounded-sm bg-neutral-800">
            <div
              className="h-full origin-left animate-grow-x rounded-sm bg-primary"
              style={{ width: `${Math.min(100, ((p.active_days_in_window ?? 0) / 84) * 100)}%` }}
            />
          </div>
        </Stat>
        <Stat
          icon={<Hourglass />}
          k="Crypto tenure"
          v={years != null ? `${years} yrs` : "–"}
          s={`${label(p.tenure_segment)} · since ${day(p.first_crypto_commit_date)}`}
        />
        <Stat
          icon={<Blocks />}
          k="Chains"
          v={fmt(tops.length)}
          s={`${p.exclusivity === "UNKNOWN" ? "Exclusivity n/a" : label(p.exclusivity)} · ${fmt(subs.length)} projects`}
        />
        <Stat
          icon={<Clock />}
          k="Last crypto activity"
          v={<span className="text-xl">{day(p.last_crypto_activity_date)}</span>}
          s={`${fmt(p.commit_count_excluding_inherited)} original commits`}
        />
      </div>
      <Callout
        icon={<Lightbulb />}
        iconClass={CALLOUT[p.priority_cohort ?? "HOLD"]}
        className={CALLOUT_BORDER[p.priority_cohort ?? "HOLD"]}
        title={`Why ${p.priority_cohort}`}
      >
        <p>{capitalize(p.priority_cohort_reason)}.</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Rule {p.priority_cohort_rule ?? "–"} · draft assumption, not yet confirmed by the client
        </p>
      </Callout>
      {flags.length > 0 && (
        <Callout
          icon={<TriangleAlert />}
          iconClass="bg-warn-soft text-warn"
          title="Check before contacting"
          className="border-[color-mix(in_srgb,var(--p3-mark)_35%,transparent)]"
        >
          <ul className="mt-1 list-disc pl-4 text-muted-foreground">
            {flags.map((f) => (
              <li key={f}>{FLAG_INFO[f]}</li>
            ))}
          </ul>
        </Callout>
      )}
      <EnrichmentGate id={p.person_id} aiEnriched={!!p.ai_enriched} />
      <Section title="Chains">
        <div className="flex flex-wrap gap-1.5">
          {tops.length ? (
            tops.map((e) => (
              <Tip key={e.ecosystem_name} tip={ecoTip(e)}>
                <span className={tagClass}>
                  <Hexagon className="size-3 text-muted-foreground" />
                  {e.ecosystem_name}
                </span>
              </Tip>
            ))
          ) : (
            <span className="text-faint">None</span>
          )}
        </div>
      </Section>
      {subs.length > 0 && (
        <Section title="Projects">
          <div className="flex flex-wrap gap-1.5">
            {subs.slice(0, 24).map((e) => (
              <Tip key={e.ecosystem_name} tip={ecoTip(e)}>
                <span className={tagClass}>{e.ecosystem_name}</span>
              </Tip>
            ))}
            {subs.length > 24 && <span className={cn(tagClass, "text-faint")}>+{subs.length - 24} more</span>}
          </div>
        </Section>
      )}
      <Section title="Top original crypto repos">
        <div className="overflow-hidden rounded-lg bg-background">
          {d.top_repos.length ? (
            d.top_repos.map((r) => {
              const live = !!window && !!r.last_original_date && r.last_original_date >= window;
              return (
                <div
                  key={r.repo_name}
                  className="flex flex-wrap items-center gap-3 border-b border-divider px-3.5 py-3 last:border-0 sm:flex-nowrap"
                >
                  <Tip tip={live ? "Active in the last 84 days" : "Not active in the last 84 days"}>
                    <span
                      className={cn(
                        "size-2 shrink-0 rounded-full bg-border-strong",
                        live && "bg-good shadow-[0_0_0_3px_color-mix(in_srgb,var(--good)_22%,transparent)]",
                      )}
                    />
                  </Tip>
                  <span className="min-w-0 flex-1 truncate font-medium">
                    {r.repo_url ? (
                      <a href={r.repo_url} target="_blank" rel="noopener" className="text-primary hover:text-brand-400">
                        {r.repo_name}
                      </a>
                    ) : (
                      r.repo_name
                    )}
                  </span>
                  <span className="flex w-full shrink-0 gap-3 text-xs text-muted-foreground sm:w-auto [&_svg]:size-3.5 [&>span]:inline-flex [&>span]:items-center [&>span]:gap-1">
                    <span>
                      <Star />
                      {fmt(r.num_stars)}
                    </span>
                    <span>
                      <CalendarDays />
                      {fmt(r.active_days)} days
                    </span>
                    <span>
                      <Clock />
                      {day(r.last_original_date)}
                    </span>
                  </span>
                </div>
              );
            })
          ) : (
            <EmptyState icon={FolderX} title="No original crypto repos">
              Their commits are in forks or non-crypto repos.
            </EmptyState>
          )}
        </div>
      </Section>
    </>
  );
}

function Contact({ d }: { d: PersonDetail }) {
  const usable = d.contacts.filter((c) => !c.is_github_noreply && !c.is_placeholder).length;
  const copy = async (v: string) => {
    try {
      await navigator.clipboard.writeText(v);
      toast.success("Email copied");
    } catch {
      toast.error("Couldn't copy. Select the text instead.");
    }
  };
  return (
    <>
      <GithubProfileSection id={d.person.person_id} />
      <Callout
        icon={<MailQuestion />}
        iconClass="bg-warn-soft text-warn"
        title="Unverified emails"
        className="border-[color-mix(in_srgb,var(--p3-mark)_35%,transparent)] text-muted-foreground"
      >
        These are commit-author addresses, not confirmed contact details. Don't infer an employer from the domain.{" "}
        {!usable && <b className="text-foreground">No usable address: only GitHub noreply or shared placeholders.</b>}
      </Callout>
      <div className="overflow-hidden rounded-lg bg-background">
        {d.contacts.length ? (
          d.contacts.map((c) => (
            <div
              key={c.value}
              className="flex flex-wrap items-center gap-2.5 border-b border-divider px-3.5 py-3 last:border-0 sm:flex-nowrap"
            >
              <span className="w-full font-mono text-[13px] break-all sm:w-auto sm:min-w-0 sm:flex-1">{c.value}</span>
              {c.is_github_noreply && (
                <span className={tagClass}>
                  <GithubIcon className="size-3" /> noreply
                </span>
              )}
              {c.is_placeholder && (
                <Tip tip={`Used by ${fmt(c.shared_by_n_developers)} different developers`}>
                  <span className={cn(tagClass, "bg-warn-soft text-warn")}>
                    <Users className="size-3" /> shared
                  </span>
                </Tip>
              )}
              <span className="text-xs whitespace-nowrap text-muted-foreground">
                {fmt(c.n_commits)} commits · last {day(c.last_seen_at)}
              </span>
              <IconButton label={`Copy ${c.value}`} tip="Copy" size="icon-sm" onClick={() => copy(c.value)}>
                <Copy className="size-3.5" />
              </IconButton>
            </div>
          ))
        ) : (
          <EmptyState icon={MailX} title="No emails">
            No commit-author email is on record.
          </EmptyState>
        )}
      </div>
    </>
  );
}

function Repos({ d }: { d: PersonDetail }) {
  return (
    <>
      <div className="overflow-x-auto rounded-lg bg-background">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="[&>th]:border-b [&>th]:border-divider [&>th]:px-3 [&>th]:py-3 [&>th]:text-left [&>th]:text-xs [&>th]:font-normal [&>th]:whitespace-nowrap [&>th]:text-muted-foreground">
              <th>Repo</th>
              <th className="text-right!">Commits</th>
              <th className="text-right!">Active days</th>
              <th>First</th>
              <th>Last</th>
            </tr>
          </thead>
          <tbody>
            {d.repos.map((r) => (
              <tr
                key={r.repo_name}
                className="[&>td]:border-b [&>td]:border-divider [&>td]:px-3 [&>td]:py-2.5 [&>td]:whitespace-nowrap last:[&>td]:border-0"
              >
                <td>
                  {r.repo_url ? (
                    <a href={r.repo_url} target="_blank" rel="noopener" className="text-primary hover:text-brand-400">
                      {r.repo_name}
                    </a>
                  ) : (
                    r.repo_name
                  )}
                  {r.inherited_history && (
                    <Tip tip="Fork or copied history: commits may not be theirs">
                      <span className={cn(tagClass, "ml-2 bg-warn-soft text-warn")}>
                        <GitFork className="size-3" />
                        fork
                      </span>
                    </Tip>
                  )}
                </td>
                <td className="text-right tabular-nums">{fmt(r.commits)}</td>
                <td className="text-right tabular-nums">{fmt(r.active_days)}</td>
                <td className="tabular-nums">{day(r.first_active_date)}</td>
                <td className="tabular-nums">{day(r.last_active_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {d.repo_total > d.repos.length && (
        <p className="text-[12.5px] text-faint">
          Showing the {d.repos.length} most recent of {fmt(d.repo_total)} repos.
        </p>
      )}
    </>
  );
}

function Details({ d }: { d: PersonDetail }) {
  const p = d.person;
  const apiLogin = (p.github_login_source ?? "").startsWith("GITHUB_API_");
  const rows: [string, ReactNode][] = [
    [
      "Person id",
      <span key="v" className="font-mono">
        {p.person_id}
      </span>,
    ],
    ["GitHub match", `${label(p.github_confidence)} · ${p.github_resolution_method ?? "–"}`],
    [
      "GitHub login source",
      apiLogin
        ? `GitHub API (${p.github_login_source === "GITHUB_API_COMMIT_API" ? "commit author" : "account id"}), ${day(p.github_login_looked_up_at)}`
        : (p.github_login_source ?? "–"),
    ],
    [
      "GitHub user id",
      <span key="v" className="font-mono">
        {p.github_user_id ?? "–"}
      </span>,
    ],
    ["First commit (any repo)", day(p.first_commit_date)],
    ["First original crypto commit", day(p.first_crypto_commit_date)],
    ["Last activity (any repo)", day(p.last_activity_date)],
    ["Commits (original only)", `${fmt(p.commit_count)} (${fmt(p.commit_count_excluding_inherited)})`],
    ["Repos (without forks)", `${fmt(p.repository_count)} (${fmt(p.repository_count_excluding_inherited)})`],
    [
      "AI enriched",
      p.ai_enriched
        ? ["Yes", p.ai_enriched_by && `by ${p.ai_enriched_by}`, p.ai_enriched_at && day(p.ai_enriched_at)]
            .filter(Boolean)
            .join(" · ")
        : "No",
    ],
    ["EC contribution rank", p.odd_contribution_rank_asof || "–"],
    ["Exclusivity", `${label(p.exclusivity)}${p.exclusivity === "UNKNOWN" ? " (no chain-mapped work in window)" : ""}`],
    [
      "Snapshot",
      <span key="v" className="font-mono">
        {p.source_snapshot_id}
      </span>,
    ],
    ["Activity window", `${day(p.activity_window_start)} → ${day(p.as_of_activity_date)}`],
  ];
  return (
    <>
      <dl className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-x-[18px] gap-y-3.5 rounded-lg bg-background p-4">
        {rows.map(([k, v]) => (
          <div key={k} className="flex min-w-0 flex-col gap-0.5">
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="font-medium break-words tabular-nums">{v}</dd>
          </div>
        ))}
      </dl>
      <Section title={`Developer ids (${d.members.length})`}>
        <div className="flex flex-wrap gap-1.5">
          {d.members.map((m) => (
            <Tip
              key={m.canonical_developer_id}
              tip={`${fmt(m.n_commits)} commits · ${m.link_method.toLowerCase().replaceAll("_", " ")}`}
            >
              <span className={cn(tagClass, "font-mono")}>{m.canonical_developer_id}</span>
            </Tip>
          ))}
        </div>
      </Section>
    </>
  );
}

function EnrichmentGate({ id, aiEnriched }: { id: string; aiEnriched: boolean }) {
  return (
    <>
      {aiEnriched ? <EnrichmentSection id={id} /> : null}
      {!aiEnriched ? <ComponentsSection id={id} /> : null}
    </>
  );
}
