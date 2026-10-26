import { Link } from "@tanstack/react-router";
import { CircleHelp, Sprout } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { tour } from "@/features/tour/tour-store";
import { DataNotes } from "./data-notes";
import { ShortlistSheet } from "./shortlist-sheet";

const link = "text-[15px] text-foreground transition-colors hover:text-primary sm:text-sm";
const active = "text-primary!";

function NavLinks({ className }: { className: string }) {
  return (
    <nav className={className} aria-label="Views">
      <Link
        to="/"
        className={link}
        activeProps={{ className: active, "aria-current": "page" }}
        activeOptions={{ exact: true, includeSearch: false }}
      >
        Overview
      </Link>
      <Link
        to="/explore"
        className={link}
        activeProps={{ className: active, "aria-current": "page" }}
        activeOptions={{ includeSearch: false }}
      >
        Explore
      </Link>
      <Link
        to="/jobs"
        className={link}
        activeProps={{ className: active, "aria-current": "page" }}
        activeOptions={{ includeSearch: false }}
      >
        Jobs
      </Link>
    </nav>
  );
}

export function TopBar() {
  return (
    <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-md">
      {/* Phones: logo and actions on the first row, the page links on a second row. sm and up: one row. */}
      <div className="mx-auto flex max-w-[1240px] flex-wrap items-center gap-x-3 gap-y-3.5 px-4 pt-3.5 pb-3 sm:flex-nowrap sm:gap-8 sm:px-8 sm:py-5">
        <div className="mr-auto flex min-w-0 items-center gap-8">
          <Link to="/" className="flex shrink-0 items-center gap-2.5 text-[17px] font-medium">
            <span className="grid size-7 place-items-center rounded-lg border border-primary text-primary shadow-[0_0_16px_color-mix(in_srgb,var(--primary)_35%,transparent)]">
              <Sprout className="size-4" />
            </span>
            <span className="max-[379px]:hidden sm:hidden md:inline">Talent Seed</span>
          </Link>
          <NavLinks className="hidden gap-6 sm:flex" />
        </div>
        <div className="flex shrink-0 items-center gap-2 text-[13px] sm:gap-3">
          <DataNotes />
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={tour.start}
                aria-label="Take the tour"
                className="grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-foreground/7 hover:text-foreground"
              >
                <CircleHelp className="size-4" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Take the tour</TooltipContent>
          </Tooltip>
          <ShortlistSheet />
        </div>
        <NavLinks className="flex w-full gap-6 sm:hidden" />
      </div>
      <div className="mx-auto max-w-[1240px] px-4 sm:px-8">
        <div className="hr-fade" />
      </div>
    </header>
  );
}
