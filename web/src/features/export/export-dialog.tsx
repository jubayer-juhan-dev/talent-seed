import { Building2, Copyright, Download, FlaskConical, MailQuestion, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { withKey } from "@/api/access-key";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { fmt } from "@/lib/format";
import { useShortlist } from "@/lib/shortlist";
import { cn } from "@/lib/utils";
import { type ExportMode, exportDialog, useExportDialog } from "./export-store";

const LIMIT = 5000;

const params = (q: Record<string, string | undefined>) =>
  new URLSearchParams(Object.entries(q).filter((e): e is [string, string] => !!e[1])).toString();

/** CSV export of the current filter or the shortlist, with the caveats spelled out before download. */
export function ExportDialog() {
  const { open, mode, filter } = useExportDialog();
  const list = useShortlist();
  const canFilter = !!filter && filter.total > 0;
  const chosen: ExportMode | null =
    mode === "filter"
      ? canFilter
        ? "filter"
        : list.length
          ? "shortlist"
          : null
      : list.length
        ? "shortlist"
        : canFilter
          ? "filter"
          : null;

  const href =
    chosen === "filter" && filter
      ? withKey(`/api/export.csv?${params(filter.query)}`)
      : chosen === "shortlist"
        ? withKey(`/api/export.csv?${params({ ids: list.map((e) => e.person_id).join(",") })}`)
        : undefined;

  const option = (value: ExportMode, title: string, sub: string, disabled: boolean) => (
    <label
      htmlFor={`export-${value}`}
      className={cn(
        "flex cursor-pointer gap-3 rounded-xl border bg-card px-3.5 py-3 transition-colors has-[:checked]:border-primary has-[:checked]:bg-accent-soft",
        disabled && "cursor-not-allowed opacity-50",
      )}
    >
      <RadioGroupItem id={`export-${value}`} value={value} disabled={disabled} className="mt-0.5" />
      <span>
        <b className="font-semibold">{title}</b>
        <span className="block text-[12.5px] text-muted-foreground">{sub}</span>
      </span>
    </label>
  );

  return (
    <Dialog open={open} onOpenChange={(o) => !o && exportDialog.close()}>
      <DialogContent className="gap-4 sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            <Download className="size-[18px]" /> Export CSV
          </DialogTitle>
          <DialogDescription>
            For outreach tools. One row per person, with the best non-noreply email.
          </DialogDescription>
        </DialogHeader>
        <RadioGroup
          value={chosen ?? ""}
          onValueChange={(v) => exportDialog.setMode(v as ExportMode)}
          className="gap-2.5"
        >
          {option(
            "filter",
            "Current filter",
            canFilter
              ? `${fmt(Math.min(filter.total, LIMIT))} people${filter.total > LIMIT ? ` (first ${fmt(LIMIT)} of ${fmt(filter.total)})` : ""}, in the current sort order`
              : "Open Explore and set a filter first",
            !canFilter,
          )}
          {option(
            "shortlist",
            "Shortlist",
            `${fmt(list.length)} starred ${list.length === 1 ? "person" : "people"}`,
            !list.length,
          )}
        </RadioGroup>
        <div className="flex gap-3 rounded-xl bg-warn-soft px-4 py-3.5">
          <div className="grid size-8 shrink-0 place-items-center rounded-[9px] bg-card text-warn">
            <TriangleAlert className="size-4" />
          </div>
          <div className="text-[13px]">
            <h4 className="mb-1.5 font-semibold">Before you send outreach</h4>
            <ul className="flex flex-col gap-2 text-muted-foreground [&_svg]:mt-0.5 [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-warn [&>li]:flex [&>li]:gap-2">
              <li>
                <MailQuestion />
                <span>
                  Emails are <b className="text-foreground">unverified</b> commit-author addresses (column{" "}
                  <code className="font-mono text-xs">email_status</code>).
                </span>
              </li>
              <li>
                <FlaskConical />
                <span>
                  Cohorts are a <b className="text-foreground">draft</b> (column{" "}
                  <code className="font-mono text-xs">cohort_status</code>).
                </span>
              </li>
              <li>
                <Building2 />
                <span>Don't infer an employer from an email domain.</span>
              </li>
              <li>
                <Copyright />
                <span>Keep the Electric Capital CC BY 4.0 attribution (included in every row).</span>
              </li>
            </ul>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => exportDialog.close()}>
            Cancel
          </Button>
          <Button asChild={!!href} disabled={!href} className="gap-2">
            {href ? (
              <a
                href={href}
                download={chosen === "shortlist" ? "talent_seed_shortlist.csv" : "talent_seed_export.csv"}
                onClick={() => {
                  toast.success("Export started");
                  setTimeout(() => exportDialog.close(), 50);
                }}
              >
                <Download className="size-4" /> Download CSV
              </a>
            ) : (
              <span>
                <Download className="size-4" /> Download CSV
              </span>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
