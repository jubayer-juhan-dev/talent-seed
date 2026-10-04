import { $api } from "@/api/client";
import { CohortBadge } from "@/components/app/cohort-badge";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { DEFAULTS } from "./search";
import { useExplore } from "./use-explore";

const OPTIONS = [
  { value: "all", label: "All" },
  { value: "P1,P2,P3", label: "P1–P3" },
  { value: "P1" },
  { value: "P2" },
  { value: "P3" },
  { value: "HOLD" },
];

export function CohortSwitcher() {
  const { search, update } = useExplore();
  const { data } = $api.useQuery("get", "/api/meta", {}, { staleTime: Infinity });
  const counts = Object.fromEntries((data?.cohorts ?? []).map((c) => [c.k, c.n]));
  const current = search.cohort ?? DEFAULTS.cohort;
  return (
    <fieldset className="flex min-w-0 max-w-full gap-0.5 overflow-x-auto rounded-[10px] border bg-muted p-[3px]">
      <legend className="sr-only">Cohort</legend>
      {OPTIONS.map((o) => (
        <button
          key={o.value}
          type="button"
          aria-pressed={current === o.value}
          onClick={() => update({ cohort: o.value === DEFAULTS.cohort ? undefined : o.value })}
          className={cn(
            "flex shrink-0 items-center gap-2 rounded-[7px] px-3 py-1.5 text-[13px] font-medium whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring",
            current === o.value && "bg-card text-foreground shadow-sm",
          )}
        >
          {o.label ?? <CohortBadge cohort={o.value} />}
          {counts[o.value] != null && (
            <span className="text-[11.5px] text-faint tabular-nums">{fmt(counts[o.value])}</span>
          )}
        </button>
      ))}
    </fieldset>
  );
}
