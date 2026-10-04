import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ExploreSearch } from "@/features/explore/search";
import { fmt } from "@/lib/format";

export type Bar = {
  key: string;
  label: string;
  total: number;
  /** Stacked segments, left to right; their sum is `total`. */
  segments: { value: number; className: string }[];
  tip: ReactNode;
  search: ExploreSearch;
};

/** Ranked horizontal bars. Each row links to Explore filtered to that item; label and value are real text. */
export function BarList({ bars }: { bars: Bar[] }) {
  const max = Math.max(1, ...bars.map((b) => b.total));
  return (
    <ul className="flex flex-col gap-0.5">
      {bars.map((b, i) => (
        <li key={b.key}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Link
                to="/explore"
                search={b.search}
                className="-mx-2 grid grid-cols-[minmax(84px,132px)_minmax(0,1fr)_64px] items-center gap-2.5 rounded-lg px-2 py-[5px] transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
              >
                <span className="truncate text-[13px]">{b.label}</span>
                <span className="flex h-3 gap-0.5" aria-hidden>
                  {b.segments.map((s, j) => (
                    <span
                      // biome-ignore lint/suspicious/noArrayIndexKey: segments are positional
                      key={j}
                      className={`h-full origin-left animate-grow-x first:rounded-l last:rounded-r ${s.className}`}
                      style={{ width: `${(s.value / max) * 100}%`, animationDelay: `${i * 30}ms` }}
                    />
                  ))}
                </span>
                <span className="text-right text-[12.5px] text-muted-foreground tabular-nums">{fmt(b.total)}</span>
              </Link>
            </TooltipTrigger>
            <TooltipContent side="top">{b.tip}</TooltipContent>
          </Tooltip>
        </li>
      ))}
    </ul>
  );
}
