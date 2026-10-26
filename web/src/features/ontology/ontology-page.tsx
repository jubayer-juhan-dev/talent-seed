import { Search, ServerCrash } from "lucide-react";
import { useMemo, useState } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { fmt } from "@/lib/format";

const FAMILIES: { type: string; label: string; blurb: string }[] = [
  { type: "SKILL", label: "Skills", blurb: "Languages, frameworks and engineering disciplines." },
  { type: "TOOL", label: "Tools", blurb: "Libraries, platforms and software that talents build with." },
  { type: "ROLE", label: "Roles", blurb: "Job roles backed by sustained contribution evidence." },
  { type: "SYSTEM", label: "Systems", blurb: "System types and architecture domains." },
  { type: "KNOWLEDGE", label: "Knowledge", blurb: "Domain and protocol knowledge areas." },
  { type: "CAPABILITY", label: "Capabilities", blurb: "Cross-cutting capabilities shown in real work." },
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
          <span className="text-sm tabular-nums">{fmt(c.talents)}</span>
        ) : (
          <span className="rounded-full border border-foreground/15 px-2 py-0.5 text-[11px] whitespace-nowrap text-muted-foreground">
            No evidence yet
          </span>
        )}
      </div>
    </li>
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
      items: filtered.filter((c) => c.type === t).sort((a, b) => b.talents - a.talents),
    }));
    return [...known, ...extra].filter((g) => g.items.length > 0);
  }, [filtered]);

  const withEvidence = concepts.filter((c) => c.talents > 0).length;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <h1 className="mb-2 text-3xl font-medium tracking-[-0.025em] sm:text-[40px] sm:leading-[1.1]">Ontology</h1>
          <p className="max-w-[560px] text-[15px] text-muted-foreground">
            Every concept in the Talent Ontology — the skills graph behind job matching — with the number of talents who
            have evidence for it.
          </p>
          {data && (
            <p className="mt-2 text-[13px] text-muted-foreground">
              {concepts.length} concepts · {groups.length} families · {withEvidence} with evidence ·{" "}
              {concepts.length - withEvidence} awaiting evidence
            </p>
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
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <h2 className="text-[17px] font-medium">{g.label}</h2>
                <span className="text-xs text-muted-foreground">{g.items.length} concepts</span>
              </div>
              {g.blurb && <p className="mt-1 text-[13px] text-muted-foreground">{g.blurb}</p>}
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
