import { MapPin, Sparkles } from "lucide-react";
import { $api } from "@/api/client";
import { Skeleton } from "@/components/ui/skeleton";

type Evidence = {
  concept_name: string;
  concept_type: string;
  status: string;
  usage_level: string;
  confidence: number;
  source: string;
  note?: string | null;
};

const typeLabel = (t: string) => t.charAt(0) + t.slice(1).toLowerCase();

const TYPE_LABEL: Record<string, string> = {
  SKILL: "Skills",
  TOOL: "Tools",
  ROLE: "Inferred roles",
  KNOWLEDGE: "Knowledge",
  CAPABILITY: "Capabilities",
  SYSTEM: "Systems",
};

/** AI enrichment (Neon): LLM summary, inferred roles, evidence rows. */
export function EnrichmentSection({ id }: { id: string }) {
  const { data, error, isPending } = $api.useQuery("get", "/api/person/enrichment", {
    params: { query: { id } },
  });
  if (isPending)
    return (
      <section>
        <Skeleton className="h-36 rounded-lg" />
      </section>
    );
  if (error || !data?.enriched) return null;

  const roles = (data.evidence ?? []).filter((e: Evidence) => e.concept_type === "ROLE" && e.status === "INFERENCE");
  const facts = (data.evidence ?? []).filter((e: Evidence) => e.status === "FACT");
  const byType = new Map<string, Evidence[]>();
  for (const e of facts) {
    const list = byType.get(e.concept_type) ?? [];
    list.push(e);
    byType.set(e.concept_type, list);
  }

  return (
    <>
      <section className="flex flex-col gap-3">
        <h3 className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Sparkles className="size-3.5 text-primary" /> AI summary
          {data.llm_model && <span>· {data.llm_model}</span>}
        </h3>
        {data.summary && <p className="text-sm leading-[1.65] text-pretty">{data.summary}</p>}
        {data.location_text && (
          <p className="flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <MapPin className="size-3.5" />
            {data.location_text}
            {data.location_confidence != null && ` · ${Math.round(data.location_confidence * 100)}% confidence`}
          </p>
        )}
        {data.seniority_band && data.seniority_band !== "unknown" && (
          <p className="text-xs text-muted-foreground">
            Seniority: <span className="text-foreground capitalize">{data.seniority_band}</span>
            {data.seniority_confidence != null && ` · ${Math.round(data.seniority_confidence * 100)}% confidence`}
          </p>
        )}
      </section>

      {roles.length > 0 && (
        <section className="flex flex-col gap-3.5">
          <h3 className="text-[15px] font-medium">Role fit</h3>
          {roles.map((r: Evidence) => {
            const pct = `${Math.round(r.confidence * 100)}%`;
            return (
              <div key={r.concept_name} className="flex flex-col gap-1.5">
                <div className="flex justify-between gap-3 text-sm">
                  <span className="font-medium">{r.concept_name}</span>
                  <span className="text-brand-300 tabular-nums">{pct}</span>
                </div>
                <span className="block h-1 rounded-sm bg-neutral-800">
                  <span
                    className="block h-full origin-left animate-grow-x rounded-sm bg-primary"
                    style={{ width: pct }}
                  />
                </span>
                {r.note && <p className="text-xs leading-[1.55] text-muted-foreground">{r.note}</p>}
              </div>
            );
          })}
        </section>
      )}

      {data.components && data.components.length > 0 && <ComponentsList components={data.components} />}

      {[...byType.entries()].map(([type, list]) => (
        <section key={type} className="flex flex-col gap-2.5">
          <h3 className="text-[15px] font-medium">{TYPE_LABEL[type] ?? typeLabel(type)}</h3>
          <div className="flex flex-wrap gap-1.5">
            {list.map((e: Evidence) => (
              <span
                key={e.concept_name}
                title={`${e.source}${e.note ? ` — ${e.note}` : ""}`}
                className="inline-flex items-center gap-2 rounded-full bg-background px-2.5 py-[5px] text-xs whitespace-nowrap"
              >
                {e.concept_name}
                <span className="text-brand-300 tabular-nums">{Math.round(e.confidence * 100)}%</span>
              </span>
            ))}
          </div>
        </section>
      ))}
    </>
  );
}

type ComponentRow = {
  component_id: string;
  component_name: string;
  usage_level: string;
  proof?: string | null;
};

export function ComponentsList({ components }: { components: ComponentRow[] }) {
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="text-[15px] font-medium">Components</h3>
      {components.map((c) => (
        <div
          key={c.component_id}
          className="flex items-center justify-between gap-3 rounded-lg bg-background px-3.5 py-3"
        >
          <span className="min-w-0">
            <span className="block text-sm font-medium">{c.component_name}</span>
            {c.proof && <span className="mt-0.5 block text-xs text-muted-foreground">{c.proof}</span>}
          </span>
          <span className="shrink-0 rounded-md border border-primary px-2.5 py-[3px] text-[11px] tracking-wide text-primary capitalize">
            {c.usage_level.replace("_USAGE", "").toLowerCase()}
          </span>
        </div>
      ))}
    </section>
  );
}

/** Components-only section: shown on any profile that has component
 *  evidence, even when the person is not AI-enriched. */
export function ComponentsSection({ id }: { id: string }) {
  const { data } = $api.useQuery("get", "/api/person/enrichment", {
    params: { query: { id } },
  });
  if (!data?.components || data.components.length === 0) return null;
  return <ComponentsList components={data.components} />;
}
