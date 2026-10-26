import { cn } from "@/lib/utils";

export type CoverageState = "covered" | "partial" | "missing" | "unscored";

const LABEL: Record<CoverageState, string> = {
  covered: "Covered",
  partial: "Partial",
  missing: "Missing",
  unscored: "Not scored",
};

/** Filled check = covered, half disc = partial, dashed ring = missing. Drawn inline so the three read as one set. */
export function CoverageIcon({ state, className }: { state: string; className?: string }) {
  const cls = cn("size-3.5 shrink-0", className);
  if (state === "covered")
    return (
      <svg viewBox="0 0 16 16" className={cn(cls, "text-primary")} aria-hidden>
        <circle cx="8" cy="8" r="7.5" fill="currentColor" />
        <path
          d="M4.8 8.3l2.1 2.1 4.3-4.6"
          fill="none"
          stroke="var(--background)"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  if (state === "partial")
    return (
      <svg viewBox="0 0 16 16" className={cn(cls, "text-brand-400")} aria-hidden>
        <circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 1.25a6.75 6.75 0 0 0 0 13.5z" fill="currentColor" />
      </svg>
    );
  if (state === "unscored")
    return (
      <svg viewBox="0 0 16 16" className={cn(cls, "text-faint")} aria-hidden>
        <circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
        <path d="M5 8h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    );
  return (
    <svg viewBox="0 0 16 16" className={cn(cls, "text-faint")} aria-hidden>
      <circle cx="8" cy="8" r="6.75" fill="none" stroke="currentColor" strokeWidth="1.5" strokeDasharray="2.6 2.2" />
    </svg>
  );
}

export function CoverageLegend({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-wrap gap-5 text-xs text-muted-foreground", className)}>
      {(["covered", "partial", "missing", "unscored"] as const).map((s) => (
        <span key={s} className="flex items-center gap-1.5">
          <CoverageIcon state={s} />
          {LABEL[s]}
          {s === "unscored" && <span className="text-faint">(no talent has evidence yet, left out of the score)</span>}
        </span>
      ))}
    </div>
  );
}

export const coverageLabel = (state: string) => LABEL[state as CoverageState] ?? state;
