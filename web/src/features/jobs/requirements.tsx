import { BookOpen, Box, Hammer, type LucideIcon, Plus, Sparkles, Tag, UserRound, Wrench, X } from "lucide-react";
import { useState } from "react";
import { $api } from "@/api/client";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

export type JobRequirement = components["schemas"]["JobRequirement"];

/** Ontology concept types → icon and display name. */
const TYPE_ICON: Record<string, LucideIcon> = {
  ROLE: UserRound,
  SKILL: Wrench,
  SYSTEM: Box,
  TOOL: Hammer,
  CAPABILITY: Sparkles,
  KNOWLEDGE: BookOpen,
};
export const typeIcon = (t: string) => TYPE_ICON[t] ?? Tag;
export const typeLabel = (t: string) => t.charAt(0) + t.slice(1).toLowerCase();

/** Every ontology concept with how many talents have evidence for it. */
const useConcepts = () => $api.useQuery("get", "/api/concepts", {}, { staleTime: 5 * 60_000 });

/** One requirement as a tile: solid for required, dashed outline for nice-to-have. */
export function RequirementChip({ req, talents }: { req: JobRequirement; talents?: number }) {
  const Icon = typeIcon(req.concept_type);
  const required = req.requirement === "required";
  const noData = talents === 0;
  return (
    <div
      title={req.evidence_text ? `“${req.evidence_text}”` : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3.5 py-2.5",
        required ? "bg-background elev-sm" : "border border-dashed border-divider",
      )}
    >
      <Icon className={cn("size-4 shrink-0", required ? "text-primary" : "text-neutral-500")} />
      <span className={cn("text-sm", required && "font-medium")}>{req.concept_name}</span>
      <span className="text-[11px] text-muted-foreground">{typeLabel(req.concept_type)}</span>
      {noData && (
        <span
          className="rounded bg-muted px-1.5 py-px text-[10px] text-faint"
          title="No talent has evidence for this yet, so it is left out of match scores"
        >
          no data yet
        </span>
      )}
    </div>
  );
}

/** Required (wide column) and nice-to-have (narrow column), as in the job header card. */
export function RequirementGroups({ requirements }: { requirements: JobRequirement[] }) {
  const { data: concepts } = useConcepts();
  const talents = new Map(concepts?.map((c) => [c.concept_id, c.talents]));
  const required = requirements.filter((r) => r.requirement === "required");
  const nice = requirements.filter((r) => r.requirement !== "required");
  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
      {[
        { label: "Required", items: required },
        { label: "Nice to have", items: nice },
      ].map((g) => (
        <div key={g.label}>
          <div className="mb-3 text-xs text-muted-foreground">
            {g.label} · {g.items.length}
          </div>
          <div className="flex flex-wrap gap-2.5">
            {g.items.map((r) => (
              <RequirementChip
                key={`${r.concept_name}-${r.requirement}`}
                req={r}
                talents={r.concept_id ? talents.get(r.concept_id) : undefined}
              />
            ))}
            {g.items.length === 0 && <span className="text-sm text-faint">None</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

type Concept = components["schemas"]["Concept"];

/** Ontology concept types in display order, with their plural group names. */
const TYPE_ORDER = ["ROLE", "SKILL", "TOOL", "SYSTEM", "KNOWLEDGE", "CAPABILITY"];
const TYPE_PLURAL: Record<string, string> = {
  ROLE: "Roles",
  SKILL: "Skills",
  TOOL: "Tools",
  SYSTEM: "Systems",
  KNOWLEDGE: "Knowledge",
  CAPABILITY: "Capabilities",
};

/** Searchable list of every ontology concept not already on the job, grouped by type. */
function ConceptPicker({ exclude, onPick }: { exclude: Set<string>; onPick: (c: Concept) => void }) {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useConcepts();
  const available = (data ?? []).filter((c) => !exclude.has(c.concept_id));
  const types = [...TYPE_ORDER, ...new Set(available.map((c) => c.type).filter((t) => !TYPE_ORDER.includes(t)))];
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-9 border-dashed px-3">
          <Plus /> Add requirement
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(380px,calc(100vw-24px))] p-0">
        <Command>
          <CommandInput placeholder="Search roles, skills, tools…" />
          <CommandList className="max-h-[340px]">
            <CommandEmpty>{isLoading ? "Loading the ontology…" : "No matching concept."}</CommandEmpty>
            {types.map((t) => {
              const items = available.filter((c) => c.type === t);
              if (!items.length) return null;
              const Icon = typeIcon(t);
              return (
                <CommandGroup key={t} heading={`${TYPE_PLURAL[t] ?? typeLabel(t)} · ${items.length}`}>
                  {items.map((c) => (
                    <CommandItem
                      key={c.concept_id}
                      value={`${c.name} ${c.aliases.join(" ")} ${c.concept_id}`}
                      onSelect={() => {
                        onPick(c);
                        setOpen(false);
                      }}
                      className="items-start gap-2.5 py-2"
                    >
                      <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-2">
                          <span className="font-medium">{c.name}</span>
                          <span
                            className={cn(
                              "ml-auto text-[11px] tabular-nums",
                              c.talents ? "text-muted-foreground" : "text-faint",
                            )}
                          >
                            {c.talents ? `${c.talents.toLocaleString("en-US")} talents` : "no data yet"}
                          </span>
                        </div>
                        {c.definition && (
                          <div className="line-clamp-2 text-xs text-muted-foreground">{c.definition}</div>
                        )}
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

/** Edit a job's requirement set: add ontology concepts, remove rows, flip required <-> nice-to-have.
 *  Used for the review step after Luna extraction and for later edits on the job page. */
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
  const add = (c: Concept) =>
    onChange([
      ...value,
      {
        concept_id: c.concept_id,
        concept_name: c.name,
        concept_type: c.type,
        requirement: "required",
        status: "FACT",
        confidence: 1,
        evidence_text: null,
        source: "manual:edit",
      },
    ]);
  const chosen = new Set(value.map((r) => r.concept_id).filter((id): id is string => !!id));

  return (
    <div className="space-y-3">
      <div className="max-h-[50vh] space-y-2 overflow-y-auto pr-1">
        {value.length === 0 && <p className="text-sm text-muted-foreground">No requirements yet.</p>}
        {value.map((r, i) => {
          const Icon = typeIcon(r.concept_type);
          return (
            <div
              key={r.concept_id ?? r.concept_name}
              className="flex items-center gap-3 rounded-lg bg-background px-3 py-2 text-sm ring-1 ring-border"
            >
              <Icon className="size-4 shrink-0 text-primary" />
              <div className="min-w-0 flex-1">
                <div className="font-medium">
                  {r.concept_name}{" "}
                  <span className="text-[11px] font-normal text-muted-foreground">{typeLabel(r.concept_type)}</span>
                </div>
                {r.evidence_text && r.source !== "manual:edit" && (
                  <div className="truncate text-xs text-muted-foreground">“{r.evidence_text}”</div>
                )}
                {r.source === "manual:edit" && <div className="text-xs text-faint">Added by hand</div>}
              </div>
              <div className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
                <span className="hidden sm:inline">Nice</span>
                <Switch
                  checked={r.requirement === "required"}
                  onCheckedChange={(on) => setReq(i, on ? "required" : "nice_to_have")}
                  aria-label={`${r.concept_name} is required`}
                />
                <span className="hidden sm:inline">Required</span>
              </div>
              <button
                type="button"
                onClick={() => remove(i)}
                aria-label={`Remove ${r.concept_name}`}
                className="grid size-7 shrink-0 place-items-center rounded-md text-faint hover:bg-muted hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
          );
        })}
      </div>
      <ConceptPicker exclude={chosen} onPick={add} />
    </div>
  );
}
