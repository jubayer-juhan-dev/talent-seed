import { ArrowDownWideNarrow, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DEFAULTS, dirOf, SORTS, sortOf } from "./search";
import { useExplore } from "./use-explore";

export function SortMenu() {
  const { search, update } = useExplore();
  const current = sortOf(search);
  const reversed = dirOf(search) !== current.dir;
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="h-[42px] gap-2 px-3.5">
          <ArrowDownWideNarrow className="size-4" />
          {current.label}
          {reversed && (dirOf(search) === "asc" ? " ↑" : " ↓")}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72">
        <DropdownMenuLabel className="text-xs tracking-wider text-faint uppercase">Sort by</DropdownMenuLabel>
        {SORTS.map((s) => (
          <DropdownMenuItem
            key={s.key}
            onSelect={() => update({ sort: s.key === DEFAULTS.sort ? undefined : s.key, dir: undefined })}
            className="items-start gap-2 py-2"
          >
            <div className="flex-1">
              <div className="font-medium">{s.label}</div>
              {s.hint && <div className="text-xs text-muted-foreground">{s.hint}</div>}
            </div>
            {s.key === current.key && <Check className="mt-0.5 size-4" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
