import { Link } from "@tanstack/react-router";
import { ArrowRight, Construction } from "lucide-react";
import { $api, errorText } from "@/api/client";
import { CohortBadge } from "@/components/app/cohort-badge";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { COHORT_DESC, COHORTS, fmt } from "@/lib/format";

const BAR: Record<string, string> = { P1: "bg-p1", P2: "bg-p2", P3: "bg-p3", HOLD: "bg-hold" };

/** Overview. Plan step 2 shows the cohort cards; charts arrive in step 5. */
export function OverviewPage() {
  const { data, error } = $api.useQuery("get", "/api/overview");
  const counts = Object.fromEntries((data?.cohorts ?? []).map((c) => [c.k, c.n]));
  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
      <h1 className="text-2xl font-bold tracking-tight">Crypto developer talent</h1>
      <p className="mt-1 mb-5 max-w-3xl text-muted-foreground">
        Who the most active open-source crypto developers are, by chain and cohort.
      </p>
      {error && <p className="mb-4 text-destructive">{errorText(error)}</p>}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {COHORTS.map((k) =>
          data ? (
            <Link key={k} to="/explore" search={k === "P1" ? {} : { cohort: k }} className="group">
              <Card className="relative gap-1.5 overflow-hidden px-[18px] py-4 transition-all hover:-translate-y-0.5 hover:shadow-md">
                <span className={`absolute inset-x-0 top-0 h-[3px] ${BAR[k]}`} />
                <div className="flex items-center justify-between">
                  <CohortBadge cohort={k} />
                  <ArrowRight className="size-4 text-faint transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
                </div>
                <div className="text-[28px] font-bold tracking-tight tabular-nums">{fmt(counts[k])}</div>
                <div className="text-[12.5px] text-muted-foreground">{COHORT_DESC[k]}</div>
              </Card>
            </Link>
          ) : (
            <Skeleton key={k} className="h-[112px] rounded-xl" />
          ),
        )}
      </div>
      <Card className="mt-4 flex-row items-start gap-3 px-[18px] py-4 text-[13px] text-muted-foreground">
        <Construction className="mt-0.5 size-4 shrink-0" />
        <span>
          <b className="text-foreground">New app, in progress.</b> This is the React rebuild of the viewer. Charts,
          Explore filters and profiles arrive in the next steps; the current app keeps working at the main link until
          the switch-over.
        </span>
      </Card>
    </div>
  );
}
