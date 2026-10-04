import { cn } from "@/lib/utils";

const STYLE: Record<string, string> = {
  P1: "bg-p1-soft text-p1",
  P2: "bg-p2-soft text-p2",
  P3: "bg-p3-soft text-p3",
  HOLD: "bg-hold-soft text-hold",
};

export function CohortBadge({ cohort, className }: { cohort: string | null | undefined; className?: string }) {
  if (!cohort) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 font-mono text-[11.5px] font-bold tracking-wide",
        STYLE[cohort] ?? STYLE.HOLD,
        className,
      )}
    >
      {cohort}
    </span>
  );
}
