import { SearchCode } from "lucide-react";
import { Card } from "@/components/ui/card";

/** Explore. Filters, results, cards/table arrive in plan step 3. */
export function ExplorePage() {
  return (
    <Card className="animate-in fade-in items-center gap-2 px-6 py-16 text-center text-muted-foreground">
      <div className="grid size-12 place-items-center rounded-2xl bg-muted text-faint">
        <SearchCode className="size-5" />
      </div>
      <p className="font-semibold text-foreground">Explore is coming in the next step</p>
      <p>Search, filters, cohort switcher, cards and table view.</p>
    </Card>
  );
}
