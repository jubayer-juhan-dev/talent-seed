import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FILTERS, filterValueLabel } from "./filter-menu";
import { joinList, LIST_FILTERS, type ListFilter, listOf } from "./search";
import { useExplore } from "./use-explore";

/** Active filters as removable chips. */
export function FilterChips() {
  const { search, update } = useExplore();
  const chips: { key: string; text: string; value: string; remove: () => void }[] = [];
  for (const k of LIST_FILTERS) {
    const values = listOf(search, k);
    for (const v of values)
      chips.push({
        key: `${k}:${v}`,
        // The AI-enriched values already read as a phrase ("AI enriched" / "Not AI enriched").
        text: k === "ai_enriched" ? "" : FILTERS[k].title,
        value: filterValueLabel(k, v),
        remove: () =>
          update({
            [k]: joinList(
              k,
              values.filter((x) => x !== v),
            ),
          }),
      });
  }
  if (search.q) chips.push({ key: "q", text: "Search", value: search.q, remove: () => update({ q: undefined }) });

  if (!chips.length)
    return (
      <span className="text-[13px] text-faint">
        No filters. Use <b className="text-muted-foreground">Filter</b> to narrow by chain, project, activity or
        country.
      </span>
    );
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <span
          key={c.key}
          className="inline-flex h-7 animate-in items-center gap-1.5 rounded-full bg-accent-soft pr-1 pl-2.5 text-[12.5px] font-medium text-primary zoom-in-90 fade-in"
        >
          {c.text && `${c.text}: `}
          <b className="font-semibold">{c.value}</b>
          <button
            type="button"
            onClick={c.remove}
            aria-label={`Remove ${[c.text, c.value].filter(Boolean).join(" ")}`}
            className="grid size-5 place-items-center rounded-full hover:bg-primary/15"
          >
            <X className="size-3.5" />
          </button>
        </span>
      ))}
      {chips.length > 1 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            update({ q: undefined, ...Object.fromEntries(LIST_FILTERS.map((k: ListFilter) => [k, undefined])) })
          }
        >
          Clear all
        </Button>
      )}
    </div>
  );
}
