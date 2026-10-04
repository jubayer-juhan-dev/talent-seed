import { Link } from "@tanstack/react-router";
import { CircleHelp, LayoutDashboard, Moon, Sprout, Sun, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { tour } from "@/features/tour/tour-store";
import { useTheme } from "@/hooks/use-theme";
import { DataNotes } from "./data-notes";
import { ShortlistSheet } from "./shortlist-sheet";

const tab =
  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13.5px] font-medium text-muted-foreground transition-colors hover:text-foreground";
const active = "bg-card text-foreground shadow-sm";

export function TopBar() {
  const { theme, toggle } = useTheme();
  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur-md backdrop-saturate-150">
      <div className="mx-auto flex max-w-[1320px] items-center gap-2 px-4 py-2.5 sm:gap-4 sm:px-5">
        <Link to="/" className="flex items-center gap-2.5 font-bold tracking-tight">
          <span className="grid size-[30px] place-items-center rounded-[9px] bg-gradient-to-br from-indigo-500 to-green-500 text-white">
            <Sprout className="size-[17px]" />
          </span>
          <span className="hidden text-[15.5px] md:inline">Talent Seed</span>
        </Link>
        <nav className="flex gap-0.5 rounded-lg border bg-muted p-[3px]" aria-label="Views">
          <Link
            to="/"
            className={tab}
            activeProps={{ className: active }}
            activeOptions={{ exact: true, includeSearch: false }}
          >
            <LayoutDashboard className="size-4" />
            <span className="hidden sm:inline">Overview</span>
          </Link>
          <Link
            to="/explore"
            className={tab}
            activeProps={{ className: active }}
            activeOptions={{ includeSearch: false }}
          >
            <Users className="size-4" />
            <span className="hidden sm:inline">Explore</span>
          </Link>
        </nav>
        <div className="flex-1" />
        <DataNotes />
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="ghost" size="icon" onClick={tour.start} aria-label="Take the tour">
              <CircleHelp className="size-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Take the tour</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              onClick={toggle}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </Button>
          </TooltipTrigger>
          <TooltipContent>{theme === "dark" ? "Light theme" : "Dark theme"}</TooltipContent>
        </Tooltip>
        <ShortlistSheet />
      </div>
    </header>
  );
}
