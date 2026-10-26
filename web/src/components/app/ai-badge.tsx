import { Sparkles } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { day } from "@/lib/format";
import { cn } from "@/lib/utils";

type Enriched = { ai_enriched?: boolean; ai_enriched_at?: string | null; ai_enriched_by?: string | null };

export const aiTip = (p: Enriched) =>
  `Profile enriched by an AI process${p.ai_enriched_by ? ` (${p.ai_enriched_by})` : ""}${p.ai_enriched_at ? ` on ${day(p.ai_enriched_at)}` : ""}`;

/** "AI enriched" badge; renders nothing when the person isn't. `compact` shows just the icon (table rows). */
export function AiBadge({ person, compact, className }: { person: Enriched; compact?: boolean; className?: string }) {
  if (!person.ai_enriched) return null;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          role="img"
          aria-label={aiTip(person)}
          className={cn(
            "inline-flex items-center gap-1 rounded-md bg-brand-800 tracking-wide whitespace-nowrap text-brand-100",
            compact ? "size-6 justify-center" : "px-2.5 py-[3px] text-[11px]",
            className,
          )}
        >
          <Sparkles className="size-3.5" />
          {!compact && "AI enriched"}
        </span>
      </TooltipTrigger>
      <TooltipContent>{aiTip(person)}</TooltipContent>
    </Tooltip>
  );
}
