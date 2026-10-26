import { Activity, Bot, GitCompare, GitMerge, Hourglass, Link2, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { PersonRow } from "@/api/client";
import { AiBadge } from "@/components/app/ai-badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { label } from "@/lib/format";
import { cn } from "@/lib/utils";

export const FLAG_INFO = {
  probable_bot: "Looks like an automation account",
  github_conflict: "Commits point at more than one GitHub account",
  linked_ids: "Several developer ids merged into this person",
  activity_table_gap: "Activity data has a gap for this person",
  bad_commit_dates: "Some commit dates are implausible",
} as const;

function Tag({
  icon,
  children,
  tone,
  tip,
}: {
  icon: ReactNode;
  children: ReactNode;
  tone?: "warn" | "bad";
  tip?: string;
}) {
  const el = (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md bg-neutral-800 px-2.5 py-[3px] text-[11px] tracking-wide whitespace-nowrap text-neutral-100 [&_svg]:size-3 [&_svg]:text-neutral-400",
        tone === "warn" && "bg-warn-soft text-warn [&_svg]:text-warn",
        tone === "bad" && "bg-destructive/12 text-destructive [&_svg]:text-destructive",
      )}
    >
      {icon}
      {children}
    </span>
  );
  if (!tip) return el;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{el}</TooltipTrigger>
      <TooltipContent>{tip}</TooltipContent>
    </Tooltip>
  );
}

/** Segments and data-quality flags as small tags, for a flex-wrap row the caller provides. */
export function PersonTags({ p }: { p: PersonRow }) {
  return (
    <>
      <AiBadge person={p} />
      <Tag icon={<Activity />}>{label(p.activity_segment)}</Tag>
      <Tag icon={<Hourglass />}>{label(p.tenure_segment)}</Tag>
      {p.exclusivity && p.exclusivity !== "UNKNOWN" && <Tag icon={<GitMerge />}>{label(p.exclusivity)}</Tag>}
      {p.flag_probable_bot && (
        <Tag icon={<Bot />} tone="bad" tip={FLAG_INFO.probable_bot}>
          Bot?
        </Tag>
      )}
      {p.flag_github_conflict && (
        <Tag icon={<GitCompare />} tone="warn" tip={FLAG_INFO.github_conflict}>
          Conflict
        </Tag>
      )}
      {p.flag_linked_ids && (
        <Tag icon={<Link2 />} tip={FLAG_INFO.linked_ids}>
          Linked
        </Tag>
      )}
      {p.flag_activity_table_gap && (
        <Tag icon={<TriangleAlert />} tone="warn" tip={FLAG_INFO.activity_table_gap}>
          Data gap
        </Tag>
      )}
    </>
  );
}
