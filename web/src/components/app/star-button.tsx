import { Star } from "lucide-react";
import { toast } from "sonner";
import { type ShortlistEntry, shortlist, useShortlist } from "@/lib/shortlist";
import { cn } from "@/lib/utils";

/** Add/remove a person from the shortlist. Stops the click so the card underneath doesn't open. */
export function StarButton({ person, className }: { person: ShortlistEntry; className?: string }) {
  const list = useShortlist();
  const on = list.some((e) => e.person_id === person.person_id);
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={on ? "Remove from shortlist" : "Add to shortlist"}
      onClick={(e) => {
        e.stopPropagation();
        shortlist.toggle({
          person_id: person.person_id,
          display_name: person.display_name,
          github_login: person.github_login,
          github_user_id: person.github_user_id,
          priority_cohort: person.priority_cohort,
          country: person.country,
        });
        toast(on ? "Removed from shortlist" : "Added to shortlist");
      }}
      onKeyDown={(e) => e.stopPropagation()}
      className={cn(
        "grid size-8 shrink-0 place-items-center rounded-lg text-primary transition-[color,background,transform] hover:bg-primary/10 active:scale-90 focus-visible:outline-2 focus-visible:outline-ring",
        className,
      )}
    >
      <Star className={cn("size-[17px]", on && "fill-primary")} />
    </button>
  );
}
