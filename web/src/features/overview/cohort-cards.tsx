import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { CohortBadge } from "@/components/app/cohort-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useCountUp } from "@/hooks/use-count-up";
import { COHORT_DESC, COHORTS, type Cohort, fmt } from "@/lib/format";

const BAR: Record<Cohort, string> = { P1: "bg-p1", P2: "bg-p2", P3: "bg-p3", HOLD: "bg-hold" };

function CohortCard({ k, n }: { k: Cohort; n: number }) {
  const value = useCountUp(n);
  return (
    <Link
      to="/explore"
      search={k === "P1" ? {} : { cohort: k }}
      className="group relative flex flex-col gap-1.5 overflow-hidden rounded-xl border bg-card px-[18px] py-4 shadow-xs transition-[transform,box-shadow,border-color] duration-200 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md focus-visible:outline-2 focus-visible:outline-ring"
    >
      <span className={`absolute inset-x-0 top-0 h-[3px] ${BAR[k]}`} />
      <div className="flex items-center justify-between">
        <CohortBadge cohort={k} />
        <ArrowRight className="size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
      </div>
      <div className="text-[28px] font-bold tracking-tight tabular-nums">
        <span aria-hidden>{fmt(value)}</span>
        <span className="sr-only">{fmt(n)} people</span>
      </div>
      <div className="text-[12.5px] text-muted-foreground">{COHORT_DESC[k]}</div>
    </Link>
  );
}

export function CohortCards({ counts }: { counts?: Record<string, number> }) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {COHORTS.map((k) =>
        counts ? (
          <CohortCard key={k} k={k} n={counts[k] ?? 0} />
        ) : (
          <Skeleton key={k} className="h-[112px] rounded-xl" />
        ),
      )}
    </div>
  );
}
