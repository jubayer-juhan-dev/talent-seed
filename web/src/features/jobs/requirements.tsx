import { useState } from "react";
import type { components } from "@/api/schema";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

export type JobRequirement = components["schemas"]["JobRequirement"];

/** Edit an extracted requirement set: remove rows, flip required <-> nice-to-have.
 *  The correction step after Luna extraction — optional, never blocks saving. */
export function RequirementsEditor({
  value,
  onChange,
}: {
  value: JobRequirement[];
  onChange: (next: JobRequirement[]) => void;
}) {
  const setReq = (i: number, requirement: string) =>
    onChange(value.map((r, j) => (j === i ? { ...r, requirement } : r)));
  const remove = (i: number) => onChange(value.filter((_, j) => j !== i));

  return (
    <div className="space-y-1.5">
      {value.length === 0 && <p className="text-sm text-muted-foreground">No requirements.</p>}
      {value.map((r, i) => (
        <div
          key={`${r.concept_name}-${r.requirement}`}
          className="flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm"
        >
          <Badge variant={r.requirement === "required" ? "default" : "secondary"}>{r.concept_type}</Badge>
          <span className="font-medium">{r.concept_name}</span>
          {r.evidence_text && (
            <span className="hidden truncate text-xs text-muted-foreground lg:inline">“{r.evidence_text}”</span>
          )}
          <span className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
            nice-to-have
            <Switch
              checked={r.requirement === "required"}
              onCheckedChange={(on) => setReq(i, on ? "required" : "nice_to_have")}
              aria-label={`required for ${r.concept_name}`}
            />
            required
          </span>
          <Button variant="ghost" size="sm" onClick={() => remove(i)} aria-label="Remove">
            ✕
          </Button>
        </div>
      ))}
    </div>
  );
}

/** Read-only grouped requirement list with evidence quotes. */
export function RequirementsList({ requirements }: { requirements: JobRequirement[] }) {
  const [q, setQ] = useState("");
  const shown = requirements.filter((r) => !q || r.concept_name.toLowerCase().includes(q.toLowerCase()));
  const group = (t: string) => shown.filter((r) => r.requirement === t);
  return (
    <div>
      {(["required", "nice_to_have"] as const).map((t) => (
        <div key={t} className="mb-3">
          <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {t === "required" ? "Required" : "Nice to have"} ({group(t).length})
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {group(t).map((r) => (
              <Badge key={`${r.concept_name}-${t}`} variant="outline" title={r.evidence_text ?? undefined}>
                {r.concept_name}
                <span className="ml-1 text-[10px] text-muted-foreground">{r.concept_type}</span>
              </Badge>
            ))}
          </div>
        </div>
      ))}
      {requirements.length > 12 && (
        <input
          className="mt-1 w-full rounded-md border px-2 py-1 text-sm"
          placeholder="Filter requirements…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      )}
    </div>
  );
}
