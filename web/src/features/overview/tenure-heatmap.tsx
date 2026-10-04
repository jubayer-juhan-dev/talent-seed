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
  "flex h-[62px] flex-col items-center justify-center rounded-lg font-semibold tabular-nums transition-[transform,box-shadow] duration-150 hover:scale-[1.04] hover:shadow-[0_0_0_2px_var(--card),0_0_0_4px_var(--ring)] focus-visible:scale-[1.04] focus-visible:shadow-[0_0_0_2px_var(--card),0_0_0_4px_var(--ring)] focus-visible:outline-none";

/** 3×3 heatmap of P1–P3 people, as a real table. One-hue sequential ramp; the value is printed in every cell. */
export function TenureHeatmap({ mix }: { mix: Overview["mix"] }) {
  const cell = (t: string, a: string) => mix.find((m) => m.tenure === t && m.activity === a)?.n ?? 0;
  const values = TENURE.flatMap((t) => ACTIVITY.map((a) => cell(t, a)));
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const step = (n: number) => Math.min(5, Math.floor(((n - lo) / (hi - lo + 1)) * 6));
  return (
    <table className="w-full table-fixed border-separate border-spacing-1 text-[12.5px]">
      <caption className="sr-only">P1–P3 people by tenure (rows) and activity (columns)</caption>
      <thead>
        <tr>
          <td className="w-[84px]" />
          {ACTIVITY.map((a) => (
            <th key={a} scope="col" className="pb-0.5 text-center text-xs font-normal text-muted-foreground">
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
              const s = step(n);
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
                          background: `var(--heat-${s})`,
                          color: s >= 3 ? "var(--heat-text-hi)" : "var(--heat-text-lo)",
                        }}
                      >
                        {fmt(n)}
                        <small className="text-[11px] font-medium opacity-85">{cohort}</small>
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
