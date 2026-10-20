import { Sparkles } from "lucide-react";
import { $api } from "@/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Evidence = {
  concept_name: string;
  concept_type: string;
  status: string;
  usage_level: string;
  confidence: number;
  source: string;
  note?: string | null;
};

function ConfBar({ v }: { v: number }) {
  return (
    <div className="h-1 w-16 overflow-hidden rounded-full bg-bar-track">
      <div className="h-full rounded-full bg-violet-400" style={{ width: `${Math.round(v * 100)}%` }} />
    </div>
  );
}

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
        <Skeleton className="h-36" />
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
    <section className="space-y-3">
      <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wider text-faint uppercase">
        <Sparkles className="size-3.5 text-violet-400" /> AI enrichment
        {data.llm_model && <span className="font-normal normal-case">· {data.llm_model}</span>}
      </h3>

      {data.summary && (
        <div className="rounded-xl border border-violet-400/20 bg-violet-400/5 p-3.5">
          <p className="text-sm leading-relaxed">{data.summary}</p>
          {data.location_text && (
            <p className="text-sm mt-1 text-muted-foreground">
              📍 {data.location_text}
              {data.location_confidence != null && ` (${Math.round(data.location_confidence * 100)}% AI)`}
            </p>
          )}
          {data.seniority_band && data.seniority_band !== "unknown" && (
            <p className="mt-2 text-xs text-faint">
              Seniority: <span className="font-medium text-foreground">{data.seniority_band}</span>
              {data.seniority_confidence != null && ` (${Math.round(data.seniority_confidence * 100)}% confidence)`}
            </p>
          )}
        </div>
      )}

      {roles.length > 0 && (
        <div className="space-y-2">
          {roles.map((r: Evidence) => (
            <div key={r.concept_name} className="flex items-center justify-between gap-3 text-sm">
              <div>
                <span className="font-medium">{r.concept_name}</span>
                {r.note && <p className="mt-0.5 text-xs text-faint">{r.note}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <ConfBar v={r.confidence} />
                <span className="w-9 text-right text-xs text-faint">{Math.round(r.confidence * 100)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {[...byType.entries()].map(([type, list]) => (
        <div key={type}>
          <p className="mb-1.5 text-xs font-medium text-faint">{TYPE_LABEL[type] ?? type}</p>
          <div className="flex flex-wrap gap-1.5">
            {list.map((e: Evidence) => (
              <span
                key={e.concept_name}
                title={`${e.source}${e.note ? ` — ${e.note}` : ""}`}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-0.5 text-xs whitespace-nowrap",
                )}
              >
                {e.concept_name}
                <span className="text-faint">{Math.round(e.confidence * 100)}%</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
