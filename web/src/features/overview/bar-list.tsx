import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ExploreSearch } from "@/features/explore/search";
import { fmt } from "@/lib/format";
import { cn } from "@/lib/utils";

export type Bar = {
  key: string;
  label: string;
  total: number;
  /** Stacked segments, left to right; their sum is `total`. */
  segments: { value: number; className: string }[];
  tip: ReactNode;
  search: ExploreSearch;
};

/** Ranked horizontal bars. Each row links to Explore filtered to that item; label and value are real text.
 *  `stacked` draws thick segmented bars sized to the largest row; `track` draws a thin bar on a full-width track. */
export function BarList({ bars, variant = "stacked" }: { bars: Bar[]; variant?: "stacked" | "track" }) {
  const max = Math.max(1, ...bars.map((b) => b.total));
  const track = variant === "track";
  return (
    <ul className={cn("flex flex-col", track ? "gap-1" : "gap-1")}>
      {bars.map((b, i) => (
        <li key={b.key}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/explore"
                search={b.search}
                className={cn(
                  "-mx-2.5 grid items-center rounded-lg px-2.5 transition-colors hover:bg-foreground/5 focus-visible:bg-foreground/5 focus-visible:outline-2 focus-visible:outline-ring",
                  track
                    ? "grid-cols-[minmax(84px,120px)_minmax(0,1fr)_48px] gap-3 py-[5px] text-[13px]"
                    : "grid-cols-[minmax(84px,140px)_minmax(0,1fr)_64px] gap-4 py-[7px]",
                )}
              >
                <span className={cn("truncate", !track && "text-sm")}>{b.label}</span>
                {track ? (
                  <span className="block h-1.5 rounded-[3px] bg-neutral-800" aria-hidden>
                    {b.segments.map((s, j) => (
                      <span
                        // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional
                        key={j}
                        className={`block h-full origin-left animate-grow-x rounded-[3px] ${s.className}`}
                        style={{ width: `${(s.value / max) * 100}%`, animationDelay: `${i * 30}ms` }}
                      />
                    ))}
                  </span>
                ) : (
                  <span
                    className="flex h-2.5 origin-left animate-grow-x gap-0.5 overflow-hidden rounded-[5px]"
                    style={{ width: `${Math.max(4, (b.total / max) * 100)}%`, animationDelay: `${i * 30}ms` }}
                    aria-hidden
                  >
                    {b.segments.map((s, j) => (
                      <span
                        // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional
                        key={j}
                        className={`h-full ${s.className}`}
                        style={{ width: `${(s.value / Math.max(1, b.total)) * 100}%` }}
                      />
                    ))}
                  </span>
                )}
                <span className="text-right text-[13px] text-muted-foreground tabular-nums">{fmt(b.total)}</span>
              </Link>
            </TooltipTrigger>
            <TooltipContent side="top">{b.tip}</TooltipContent>
          </Tooltip>
        </li>
      ))}
    </ul>
  );
}
