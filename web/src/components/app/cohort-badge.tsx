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
        "inline-flex items-center rounded-full px-2.5 py-[3px] text-[11px] font-medium tracking-wide",
        STYLE[cohort] ?? STYLE.HOLD,
        className,
      )}
    >
      {cohort}
    </span>
  );
}
