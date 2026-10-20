import { Blocks, Lightbulb, MapPin } from "lucide-react";
import type { PersonRow } from "@/api/client";
import { CohortBadge } from "@/components/app/cohort-badge";
import { GithubIcon as Github } from "@/components/app/github-icon";
import { PersonAvatar } from "@/components/app/person-avatar";
import { StarButton } from "@/components/app/star-button";
import { fmt } from "@/lib/format";
import { PersonTags } from "./person-tags";

export const activeShare = (p: PersonRow) => Math.min(100, ((p.active_days_in_window ?? 0) / 84) * 100);

export function GithubLine({ p }: { p: PersonRow }) {
  if (p.github_login)
    return (
      <span className="flex items-center gap-1.5 truncate">
        <Github className="size-3.5 shrink-0" />@{p.github_login}
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
      className="flex min-w-0 animate-in cursor-pointer flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs transition-[transform,box-shadow,border-color] duration-200 fade-in fill-mode-both slide-in-from-bottom-1.5 hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md focus-visible:outline-2 focus-visible:outline-ring"
    >
      <div className="flex min-w-0 items-start gap-3">
        <PersonAvatar person={p} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14.5px] font-semibold">{p.display_name || "(no name)"}</div>
          <div className="flex text-[12.5px] text-muted-foreground">
            <GithubLine p={p} />
          </div>
        </div>
        <CohortBadge cohort={p.priority_cohort} />
        <StarButton person={p} className="-mt-1 -mr-1" />
      </div>
      <div className="flex items-start gap-1.5 text-[12.5px] text-muted-foreground">
        <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-faint" />
        <span>{p.priority_cohort_reason}</span>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Active days, last 84</span>
          <b className="font-semibold text-foreground tabular-nums">{fmt(p.active_days_in_window)}</b>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-bar-track">
          <div
            className="h-full origin-left animate-grow-x rounded-full bg-gradient-to-r from-bar-light to-bar-strong"
            style={{ width: `${activeShare(p)}%` }}
          />
        </div>
      </div>
      <PersonTags p={p} />
      <div className="mt-auto flex justify-between gap-2 border-t pt-2.5 text-xs text-muted-foreground">
        <span className="flex min-w-0 items-center gap-1.5 truncate">
          <Blocks className="size-3.5 shrink-0" />
          <span className="truncate">
            <ChainsLine p={p} />
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-1.5">
          <MapPin className="size-3.5" />
          {p.location || p.country || "–"}
        </span>
      </div>
    </div>
  );
}
