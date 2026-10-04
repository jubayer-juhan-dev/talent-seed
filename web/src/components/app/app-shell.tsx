import { Outlet } from "@tanstack/react-router";
import { $api } from "@/api/client";
import { day } from "@/lib/format";
import { TopBar } from "./top-bar";

export function AppShell() {
  const { data } = $api.useQuery("get", "/api/meta", {}, { staleTime: Infinity });
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
