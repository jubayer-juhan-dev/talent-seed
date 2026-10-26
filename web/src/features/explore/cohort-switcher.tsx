import { $api } from "@/api/client";
import { COHORT_MARK } from "@/features/overview/cohort-cards";
import { type Cohort, fmt } from "@/lib/format";
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
    <fieldset className="m-0 flex min-w-0 max-w-full flex-wrap gap-2 border-0 p-0">
      <legend className="sr-only">Cohort</legend>
      {OPTIONS.map((o) => {
        const on = current === o.value;
        const mark = COHORT_MARK[o.value as Cohort];
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={on}
            onClick={() => update({ cohort: o.value === DEFAULTS.cohort ? undefined : o.value })}
            className={cn(
              "flex shrink-0 items-center gap-2 rounded-full border border-divider bg-card px-3.5 py-2 text-[13px] font-medium whitespace-nowrap transition-colors hover:bg-[color-mix(in_srgb,var(--foreground)_6%,var(--card))] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring",
              on &&
                "border-primary bg-[color-mix(in_srgb,var(--primary)_14%,var(--card))] hover:bg-[color-mix(in_srgb,var(--primary)_18%,var(--card))]",
            )}
          >
            {mark && <span aria-hidden className="size-2 rounded-full" style={{ background: mark }} />}
            {o.label ?? o.value}
            {counts[o.value] != null && (
              <span className="font-normal text-muted-foreground tabular-nums">{fmt(counts[o.value])}</span>
            )}
          </button>
        );
      })}
    </fieldset>
  );
}
