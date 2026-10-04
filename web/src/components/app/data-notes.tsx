import { ChevronDown, Database, FlaskConical } from "lucide-react";
import { $api } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { day } from "@/lib/format";

/** The "Draft" pill in the top bar: snapshot dates and the data caveats, always one click away. */
export function DataNotes() {
  const { data } = $api.useQuery("get", "/api/meta", {}, { staleTime: Infinity });
  const run = data?.run;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
          <span className="inline-flex items-center gap-1 rounded-full bg-warn-soft px-2 py-0.5 text-[11.5px] font-semibold text-warn">
            <FlaskConical className="size-3.5" />
            Draft
          </span>
          <span className="hidden md:inline">
            {run ? `Activity through ${day(run.as_of_activity_date)}` : "Loading…"}
          </span>
          <ChevronDown className="hidden size-4 md:block" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 text-[13px]">
        <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-faint">
          <Database className="size-3.5" />
          About this data
        </div>
        <div className="space-y-3 text-muted-foreground">
          <p>
            Snapshot <b className="font-mono text-foreground">{run?.source_snapshot_id ?? "…"}</b>
            <br />
            Activity through <b className="text-foreground">{day(run?.as_of_activity_date)}</b> · built{" "}
            {run ? `${run.run_at.slice(0, 16).replace("T", " ")} UTC` : "…"}
          </p>
          <p>
            <b className="text-foreground">Cohorts are a draft.</b> The P1–P3 rules are an assumption until the client
            confirms them.
          </p>
          <p>
            <b className="text-foreground">Emails are unverified</b> commit-author addresses. Don't infer an employer
            from an email domain.
          </p>
          <p>
            Data from Electric Capital{" "}
            <a className="text-primary hover:underline" href="https://opendevdata.org" target="_blank" rel="noopener">
              Open Dev Data
            </a>
            , CC BY 4.0.
          </p>
        </div>
      </PopoverContent>
    </Popover>
  );
}
