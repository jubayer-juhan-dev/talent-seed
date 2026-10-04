import { Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { $api } from "@/api/client";
import { SEARCH_INPUT_ID } from "@/features/explore/search-input";
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
    <div className="flex min-h-svh flex-col">
      <TopBar />
      <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 pt-6 pb-10 sm:px-5">
        <Outlet />
      </main>
      <footer className="mx-auto flex w-full max-w-[1320px] flex-wrap gap-x-5 gap-y-1.5 px-4 pb-8 text-xs text-faint sm:px-5">
        <span>
          Data from Electric Capital{" "}
          <a
            className="text-muted-foreground hover:underline"
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
    </div>
  );
}
