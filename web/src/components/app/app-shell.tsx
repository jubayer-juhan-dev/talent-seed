import { Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { $api } from "@/api/client";
import { SEARCH_INPUT_ID } from "@/features/explore/search-input";
import { ExportDialog } from "@/features/export/export-dialog";
import { GuidedTour } from "@/features/tour/guided-tour";
import { day } from "@/lib/format";
import { TopBar } from "./top-bar";

export function AppShell() {
  const { data } = $api.useQuery("get", "/api/meta", {}, { staleTime: Infinity });
  const navigate = useNavigate();

  // "/" anywhere (outside inputs and dialogs) jumps to Explore's search box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      if (t.closest("input, textarea, [contenteditable], [role=dialog]")) return;
      e.preventDefault();
      const focus = () => document.getElementById(SEARCH_INPUT_ID)?.focus();
      if (document.getElementById(SEARCH_INPUT_ID)) focus();
      else navigate({ to: "/explore" }).then(() => requestAnimationFrame(focus));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate]);

  return (
    <div className="page-glow flex min-h-svh flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-[1240px] flex-1 px-4 pt-8 pb-14 sm:px-8 sm:pt-10">
        <Outlet />
      </main>
      <footer className="mx-auto flex w-full max-w-[1240px] flex-wrap gap-x-6 gap-y-2 px-4 pb-10 text-xs leading-relaxed text-muted-foreground sm:px-8">
        <span>
          Data from Electric Capital{" "}
          <a
            className="text-primary hover:text-brand-400"
            href="https://opendevdata.org"
            target="_blank"
            rel="noopener"
          >
            Open Dev Data
          </a>
          , licensed CC BY 4.0.
        </span>
        <span>Emails are unverified commit-author addresses.</span>
        <span>Cohorts are a draft (DRAFT_ASSUMPTION).</span>
        {data && (
          <span>
            Snapshot {data.run.source_snapshot_id}, activity through {day(data.run.as_of_activity_date)}.
          </span>
        )}
      </footer>
      <ExportDialog />
      <GuidedTour />
    </div>
  );
}
