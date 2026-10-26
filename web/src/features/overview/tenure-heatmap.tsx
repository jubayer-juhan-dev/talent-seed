import { Link } from "@tanstack/react-router";
import type { Overview } from "@/api/client";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmt, label } from "@/lib/format";

const TENURE = ["ESTABLISHED", "EMERGING", "NEWCOMER"] as const;
const ACTIVITY = ["FULL_TIME", "PART_TIME", "ONE_TIME"] as const;

/** Which cohort a tenure × activity cell feeds (config/talent_seed_thresholds.toml, [priority_cohort]). */
export function cohortOf(tenure: string, activity: string) {
  if (activity === "FULL_TIME") return tenure === "NEWCOMER" ? "P2" : "P1";
  if (activity === "PART_TIME") return tenure === "NEWCOMER" ? "P3" : "P2";
  return "P3";
}

const cellClass =
  "flex h-16 flex-col items-center justify-center gap-0.5 rounded-lg border border-primary/25 text-[15px] font-medium tabular-nums transition-colors duration-150 hover:border-primary focus-visible:border-primary focus-visible:outline-none";

/** 3×3 heatmap of P1–P3 people, as a real table. The accent mixed into the surface; the value is printed in every cell. */
export function TenureHeatmap({ mix }: { mix: Overview["mix"] }) {
  const cell = (t: string, a: string) => mix.find((m) => m.tenure === t && m.activity === a)?.n ?? 0;
  const values = TENURE.flatMap((t) => ACTIVITY.map((a) => cell(t, a)));
  const hi = Math.max(1, ...values);
  // the accent mixed into the surface: brighter cells hold more people
  const share = (n: number) => Math.round(12 + (n / hi) * 78);
  return (
    <table className="w-full table-fixed border-separate border-spacing-1.5 text-xs">
      <caption className="sr-only">P1–P3 people by tenure (rows) and activity (columns)</caption>
      <thead>
        <tr>
          <td className="w-[88px]" />
          {ACTIVITY.map((a) => (
            <th key={a} scope="col" className="pb-1 text-center text-xs font-normal text-muted-foreground">
              {label(a)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {TENURE.map((t) => (
          <tr key={t}>
            <th scope="row" className="text-left text-xs font-normal text-muted-foreground">
              {label(t)}
            </th>
            {ACTIVITY.map((a) => {
              const n = cell(t, a);
              const pct = share(n);
              const cohort = cohortOf(t, a);
              return (
                <td key={a} className="p-0">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Link
                        to="/explore"
                        search={{ cohort: "P1,P2,P3", tenure: t, activity: a }}
                        aria-label={`${label(t)}, ${label(a)}: ${fmt(n)} people, cohort ${cohort}`}
                        className={cellClass}
                        style={{
                          background: `color-mix(in srgb, var(--primary) ${pct}%, var(--card))`,
                          color: pct > 55 ? "var(--background)" : "var(--foreground)",
                        }}
                      >
                        {fmt(n)}
                        <small className="text-[10px] font-normal tracking-[0.04em] opacity-75">{cohort}</small>
                      </Link>
                    </TooltipTrigger>
                    <TooltipContent>
                      <b>
                        {label(t)} · {label(a)}
                      </b>
                      <br />
                      {fmt(n)} people · cohort {cohort}
                    </TooltipContent>
                  </Tooltip>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
