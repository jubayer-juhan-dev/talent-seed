import {
  BookOpen,
  Braces,
  Briefcase,
  Check,
  CircleDashed,
  Clock,
  Layers,
  type LucideIcon,
  Network,
  Search,
  Server,
  ServerCrash,
  Shapes,
  Sparkles,
  Users,
  Wrench,
} from "lucide-react";
import { useMemo, useState } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { fmt } from "@/lib/format";

const FAMILIES: { type: string; label: string; blurb: string; icon: LucideIcon }[] = [
  { type: "SKILL", label: "Skills", blurb: "Languages, frameworks and engineering disciplines.", icon: Braces },
  { type: "TOOL", label: "Tools", blurb: "Libraries, platforms and software that talents build with.", icon: Wrench },
  { type: "ROLE", label: "Roles", blurb: "Job roles backed by sustained contribution evidence.", icon: Briefcase },
  { type: "SYSTEM", label: "Systems", blurb: "System types and architecture domains.", icon: Server },
  { type: "KNOWLEDGE", label: "Knowledge", blurb: "Domain and protocol knowledge areas.", icon: BookOpen },
  {
    type: "CAPABILITY",
    label: "Capabilities",
    blurb: "Cross-cutting capabilities shown in real work.",
    icon: Sparkles,
  },
];

type ConceptItem = {
  concept_id: string;
  name: string;
  type: string;
  definition?: string | null;
  aliases: string[];
  talents: number;
};

function ConceptRow({ c, max }: { c: ConceptItem; max: number }) {
  const pct = c.talents > 0 ? Math.max(3, Math.round((c.talents / max) * 100)) : 0;
  return (
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 border-b border-foreground/8 py-2.5 last:border-b-0">
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className={c.talents ? "text-sm font-medium" : "text-sm font-medium text-muted-foreground"}>
            {c.name}
          </span>
          <span className="font-mono text-[11px] text-muted-foreground">{c.concept_id}</span>
        </div>
        {c.definition && (
          <p className="mt-0.5 line-clamp-2 text-[13px] leading-snug text-muted-foreground">{c.definition}</p>
        )}
        <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-foreground/10">
          <div className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div className="shrink-0 pt-0.5 text-right">
        {c.talents > 0 ? (
          <span className="inline-flex items-center gap-1.5 text-sm tabular-nums">
            <Users className="size-3.5 text-muted-foreground" />
            {fmt(c.talents)}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full border border-foreground/15 px-2 py-0.5 text-[11px] whitespace-nowrap text-muted-foreground">
            <CircleDashed className="size-3" />
            No evidence yet
          </span>
        )}
      </div>
    </li>
  );
}

function StatChip({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-foreground/12 bg-card px-3 py-1.5 text-[13px] text-muted-foreground">
      <Icon className="size-3.5 text-primary" />
      {children}
    </span>
  );
}

export function OntologyPage() {
  const { data, error } = $api.useQuery("get", "/api/concepts", {}, { staleTime: 5 * 60_000 });
  const [q, setQ] = useState("");

  const concepts = useMemo<ConceptItem[]>(() => (data ?? []) as ConceptItem[], [data]);
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return concepts;
    return concepts.filter(
      (c) =>
        c.name.toLowerCase().includes(needle) ||
        c.concept_id.toLowerCase().includes(needle) ||
        (c.aliases ?? []).some((a) => a.toLowerCase().includes(needle)),
    );
  }, [concepts, q]);

  const groups = useMemo(() => {
    const known = FAMILIES.map((f) => ({
      ...f,
      items: filtered
        .filter((c) => c.type === f.type)
        .sort((a, b) => b.talents - a.talents || a.name.localeCompare(b.name)),
    }));
    const extraTypes = [...new Set(filtered.map((c) => c.type))].filter((t) => !FAMILIES.some((f) => f.type === t));
    const extra = extraTypes.map((t) => ({
      type: t,
      label: t.charAt(0) + t.slice(1).toLowerCase(),
      blurb: "",
      icon: Shapes,
      items: filtered.filter((c) => c.type === t).sort((a, b) => b.talents - a.talents),
    }));
    return [...known, ...extra].filter((g) => g.items.length > 0);
  }, [filtered]);

  const withEvidence = concepts.filter((c) => c.talents > 0).length;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-3.5">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-primary/50 text-primary shadow-[0_0_18px_color-mix(in_srgb,var(--primary)_35%,transparent)]">
              <Network className="size-5" />
            </span>
            <h1 className="text-3xl font-medium tracking-[-0.025em] sm:text-[40px] sm:leading-[1.1]">Ontology</h1>
          </div>
          <p className="mt-3 max-w-[560px] text-[15px] text-muted-foreground">
            Every concept in the Talent Ontology — the skills graph behind job matching — with the number of talents who
            have evidence for it.
          </p>
          {data && (
            <div className="mt-3.5 flex flex-wrap gap-2">
              <StatChip icon={Layers}>{concepts.length} concepts</StatChip>
              <StatChip icon={Shapes}>{groups.length} families</StatChip>
              <StatChip icon={Check}>{withEvidence} with evidence</StatChip>
              <StatChip icon={Clock}>{concepts.length - withEvidence} awaiting evidence</StatChip>
            </div>
          )}
        </div>
        <label className="relative block w-full sm:w-[260px]">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search concepts…"
            className="w-full rounded-lg border border-foreground/15 bg-card py-2.5 pr-3 pl-9 text-sm outline-none placeholder:text-muted-foreground focus:border-primary"
          />
        </label>
      </header>

      {error ? (
        <div className="rounded-[14px] bg-card elev-sm">
          <EmptyState icon={ServerCrash} title="Couldn't load the ontology" error>
            {errorText(error)}
          </EmptyState>
        </div>
      ) : !data ? (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
          <Skeleton className="h-[420px] rounded-[14px]" />
          <Skeleton className="h-[420px] rounded-[14px]" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-[14px] bg-card elev-sm">
          <EmptyState icon={Search} title="No concepts match">
            Nothing in the ontology matches “{q}”.
          </EmptyState>
        </div>
      ) : (
        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
          {groups.map((g) => (
            <section key={g.type} className="flex min-w-0 flex-col rounded-[14px] bg-card p-5 elev-sm sm:p-7">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary">
                    <g.icon className="size-[18px]" />
                  </span>
                  <h2 className="text-[17px] font-medium">{g.label}</h2>
                </div>
                <span className="text-xs text-muted-foreground">
                  {g.items.length} concepts · {fmt(g.items.reduce((n, c) => n + c.talents, 0))} talents
                </span>
              </div>
              {g.blurb && <p className="mt-2 text-[13px] text-muted-foreground">{g.blurb}</p>}
              <ul className="mt-2 flex flex-col">
                {g.items.map((c) => (
                  <ConceptRow key={c.concept_id} c={c} max={Math.max(1, ...g.items.map((i) => i.talents))} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
