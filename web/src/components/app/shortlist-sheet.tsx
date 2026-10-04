import { Star, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { shortlist, useShortlist } from "@/lib/shortlist";
import { CohortBadge } from "./cohort-badge";
import { PersonAvatar } from "./person-avatar";

/** Top-bar shortlist button and drawer. Opening profiles and CSV export arrive in plan steps 4 and 6. */
export function ShortlistSheet() {
  const list = useShortlist();
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="gap-2"
          aria-label={`Shortlist, ${list.length} ${list.length === 1 ? "person" : "people"}`}
        >
          <Star className="size-4" />
          <span className="hidden sm:inline">Shortlist</span>
          <span className="grid h-[18px] min-w-[18px] place-items-center rounded-full bg-primary px-1.5 text-[11px] font-bold text-primary-foreground">
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
              <div key={p.person_id} className="flex items-center gap-3 rounded-lg p-2.5 hover:bg-muted">
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
                  onClick={() => shortlist.remove(p.person_id)}
                >
                  <Star className="size-4 fill-amber-500 text-amber-500" />
                </Button>
              </div>
            ))
          )}
        </div>
        {list.length > 0 && (
          <div className="border-t p-4">
            <Button
              variant="outline"
              className="gap-2"
              onClick={() => window.confirm(`Remove all ${list.length} people?`) && shortlist.clear()}
            >
              <Trash2 className="size-4" /> Clear
            </Button>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
