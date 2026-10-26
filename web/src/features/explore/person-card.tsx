import { Link2, MapPin } from "lucide-react";
import type { PersonRow } from "@/api/client";
import { CohortBadge } from "@/components/app/cohort-badge";
import { GithubIcon as Github } from "@/components/app/github-icon";
import { PersonAvatar } from "@/components/app/person-avatar";
import { StarButton } from "@/components/app/star-button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { fmt } from "@/lib/format";
import { PersonTags } from "./person-tags";

export const activeShare = (p: PersonRow) => Math.min(100, ((p.active_days_in_window ?? 0) / 84) * 100);

export function GithubLine({ p }: { p: PersonRow }) {
  if (p.github_login)
    return (
      <span className="flex items-center gap-1.5 truncate">
        <Github className="size-3.5 shrink-0" />
        {p.github_login}
      </span>
    );
  if (p.github_user_id != null)
    return (
      <span className="flex items-center gap-1.5 truncate text-faint">
        <Github className="size-3.5 shrink-0" />
        login not looked up
      </span>
    );
  return <span className="text-faint">No GitHub match</span>;
}

export function ChainsLine({ p }: { p: PersonRow }) {
  const c = p.top_level_ecosystems ?? [];
  if (!c.length) return <span className="text-faint">No chain</span>;
  return (
    <>
      {c.slice(0, 3).join(", ")}
      {c.length > 3 && <span className="text-faint"> +{c.length - 3}</span>}
    </>
  );
}

export function PersonCard({ p, index, onOpen }: { p: PersonRow; index: number; onOpen: () => void }) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: a card holding its own buttons can't be a <button>
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => e.key === "Enter" && onOpen()}
      aria-label={`Open ${p.display_name || "person"}`}
      style={{ animationDelay: `${Math.min(index % 50, 20) * 25}ms` }}
      className="flex min-w-0 animate-in cursor-pointer flex-col gap-4 rounded-[14px] bg-card p-5 elev-sm transition-shadow duration-200 fade-in fill-mode-both slide-in-from-bottom-1.5 hover:elev-md focus-visible:outline-2 focus-visible:outline-ring"
    >
      <div className="flex min-w-0 items-start gap-3">
        <PersonAvatar person={p} className="text-[15px]" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[15px] font-medium">{p.display_name || "(no name)"}</div>
          <div className="mt-0.5 flex text-xs text-muted-foreground">
            <GithubLine p={p} />
          </div>
        </div>
        <StarButton person={p} className="-mt-1 -mr-1.5" />
      </div>
      <div>
        <div className="mb-2 flex justify-between text-xs">
          <span className="text-muted-foreground">Active days, last 84</span>
          <span className="font-medium tabular-nums">{fmt(p.active_days_in_window)}</span>
        </div>
        <div className="h-1 overflow-hidden rounded-sm bg-neutral-800">
          <div
            className="h-full origin-left animate-grow-x rounded-sm bg-primary"
            style={{ width: `${activeShare(p)}%` }}
          />
        </div>
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <CohortBadge cohort={p.priority_cohort} />
            </span>
          </TooltipTrigger>
          <TooltipContent>{p.priority_cohort_reason}</TooltipContent>
        </Tooltip>
        <PersonTags p={p} />
      </div>
      <div className="hr-fade mt-auto" />
      <div className="flex justify-between gap-3 text-xs text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1.5">
          <Link2 className="size-3.5 shrink-0" />
          <span className="truncate">
            <ChainsLine p={p} />
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <MapPin className="size-3.5" />
          {p.location || p.country || "Unknown"}
        </span>
      </div>
    </div>
  );
}
