import { useNavigate, useRouterState } from "@tanstack/react-router";
import { Download, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { exportDialog } from "@/features/export/export-store";
import { markProfilePushed } from "@/features/profile/profile-nav";
import { shortlist, useShortlist } from "@/lib/shortlist";
import { CohortBadge } from "./cohort-badge";
import { PersonAvatar } from "./person-avatar";

/** Top-bar shortlist button and drawer. Rows open the profile; Export CSV opens the export dialog. */
export function ShortlistSheet() {
  const list = useShortlist();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const onExplore = useRouterState({ select: (s) => s.location.pathname.endsWith("/explore") });
  const openPerson = (id: string) => {
    setOpen(false);
    markProfilePushed();
    // On Explore keep the current filters; elsewhere open Explore with just the profile.
    navigate({ to: "/explore", search: (prev) => (onExplore ? { ...prev, p: id } : { p: id }) });
  };
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          data-tour="shortlist"
          variant="outline"
          className="h-9 gap-2 px-3"
          aria-label={`Shortlist, ${list.length} ${list.length === 1 ? "person" : "people"}`}
        >
          <Star className="size-4" />
          <span className="hidden sm:inline">Shortlist</span>
          <span className="grid h-[18px] min-w-[22px] place-items-center rounded-md bg-brand-800 px-1.5 text-[11px] text-brand-100 tabular-nums">
            {list.length}
          </span>
        </Button>
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 p-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle className="flex items-center gap-2">
            <Star className="size-4" /> Shortlist
          </SheetTitle>
          <SheetDescription>Starred people, kept in this browser.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-3">
          {list.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-6 py-16 text-center text-muted-foreground">
              <div className="grid size-12 place-items-center rounded-2xl bg-muted text-faint">
                <Star className="size-5" />
              </div>
              <p className="font-semibold text-foreground">Your shortlist is empty</p>
              <p>Star people in Explore to collect them here, then export them as CSV.</p>
            </div>
          ) : (
            list.map((p) => (
              // biome-ignore lint/a11y/useSemanticElements: the row holds its own remove button
              <div
                key={p.person_id}
                role="button"
                tabIndex={0}
                onClick={() => openPerson(p.person_id)}
                onKeyDown={(e) => e.key === "Enter" && openPerson(p.person_id)}
                className="flex cursor-pointer items-center gap-3 rounded-lg p-2.5 animate-in fade-in hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
              >
                <PersonAvatar person={p} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{p.display_name || "(no name)"}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {p.github_login ? `@${p.github_login}` : p.person_id}
                    {p.country ? ` · ${p.country}` : ""}
                  </div>
                </div>
                <CohortBadge cohort={p.priority_cohort} />
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove from shortlist"
                  onClick={(e) => {
                    e.stopPropagation();
                    shortlist.remove(p.person_id);
                  }}
                >
                  <Star className="size-4 fill-amber-500 text-amber-500" />
                </Button>
              </div>
            ))
          )}
        </div>
        {list.length > 0 && (
          <div className="flex gap-2 border-t p-4">
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => window.confirm(`Remove all ${list.length} people?`) && shortlist.clear()}
            >
              <Trash2 className="size-4" /> Clear
            </Button>
            <Button
              className="flex-1 gap-2"
              onClick={() => {
                setOpen(false);
                exportDialog.open("shortlist");
              }}
            >
              <Download className="size-4" /> Export CSV
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
