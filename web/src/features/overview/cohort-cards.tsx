import { Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp } from "@/hooks/use-count-up";
import { COHORT_DESC, COHORTS, type Cohort, fmt } from "@/lib/format";

export const COHORT_MARK: Record<Cohort, string> = {
  P1: "var(--p1-mark)",
  P2: "var(--p2-mark)",
  P3: "var(--p3-mark)",
  HOLD: "var(--hold-mark)",
};

function CohortCard({ k, n }: { k: Cohort; n: number }) {
  const value = useCountUp(n);
  const mark = COHORT_MARK[k];
  return (
    <Link
      to="/explore"
      search={k === "P1" ? {} : { cohort: k }}
      className="group relative flex flex-col gap-3.5 overflow-hidden rounded-[14px] bg-card px-6 py-[22px] elev-sm transition-shadow duration-200 hover:elev-md focus-visible:outline-2 focus-visible:outline-ring"
    >
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: mark }} />
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 text-xs font-medium tracking-[0.04em]">
          <span className="size-2 rounded-full" style={{ background: mark, boxShadow: `0 0 8px ${mark}` }} />
          {k}
        </span>
        <ArrowUpRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-foreground" />
      </div>
      <div className="text-[34px] leading-none font-medium tracking-[-0.025em] tabular-nums">
        <span aria-hidden>{fmt(value)}</span>
        <span className="sr-only">{fmt(n)} people</span>
      </div>
      <div className="text-[13px] leading-normal text-muted-foreground">{COHORT_DESC[k]}</div>
    </Link>
  );
}

export function CohortCards({ counts }: { counts?: Record<string, number> }) {
  return (
    <div data-tour="cohort-cards" className="grid grid-cols-1 gap-4 min-[520px]:grid-cols-2 lg:grid-cols-4">
      {COHORTS.map((k) =>
        counts ? (
          <CohortCard key={k} k={k} n={counts[k] ?? 0} />
        ) : (
          <Skeleton key={k} className="h-[142px] rounded-[14px]" />
        ),
      )}
    </div>
  );
}
