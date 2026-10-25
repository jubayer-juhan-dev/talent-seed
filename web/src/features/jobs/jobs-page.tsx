import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowUpRight, Briefcase, Building2, Loader2, Plus, Sparkles } from "lucide-react";
import { type ReactNode, useState } from "react";
import { $api, fetchClient, type Schemas } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { fmt } from "@/lib/format";
import { type JobRequirement, RequirementsEditor } from "./requirements";

type JobDetail = Schemas["JobDetail"];
type JobRow = Schemas["JobRow"];

/** Soft accent glow behind the Jobs screens (top-left), as in the design. */
export function JobsBackdrop() {
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-[560px] bg-[radial-gradient(1200px_500px_at_0%_-10%,color-mix(in_srgb,var(--primary)_10%,transparent),transparent_70%)]"
    />
  );
}

export const jobPlace = (j: { location_text?: string | null; location_country?: string | null }) =>
  j.location_text || j.location_country || null;

function Field({ label, htmlFor, children }: { label: string; htmlFor: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-xs text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function NewJobDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [extracted, setExtracted] = useState<JobDetail | null>(null);
  const [edited, setEdited] = useState<JobRequirement[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const reset = () => {
    setTitle("");
    setCompany("");
    setLocation("");
    setDescription("");
    setExtracted(null);
    setEdited([]);
    setError("");
  };

  /** The job is saved as soon as extraction succeeds; leaving the review step opens it. */
  const finish = (jobId: string) => {
    queryClient.invalidateQueries();
    onOpenChange(false);
    reset();
    navigate({ to: "/jobs/$jobId", params: { jobId } });
  };

  const runExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const res = (await fetchClient.POST("/api/jobs", {
        body: { title, company, location, description },
      })) as { data?: JobDetail; error?: unknown };
      if (!res.data)
        throw new Error(
          res.error
            ? typeof res.error === "object"
              ? JSON.stringify(res.error)
              : String(res.error)
            : "extraction failed",
        );
      setExtracted(res.data);
      setEdited(res.data.requirements);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const saveCorrected = async () => {
    if (!extracted) return;
    setSaving(true);
    try {
      await fetchClient.PATCH("/api/jobs/{job_id}/requirements", {
        params: { path: { job_id: extracted.job_id } },
        body: edited.map((r) => ({
          concept_id: r.concept_id ?? undefined,
          concept_name: r.concept_name,
          concept_type: r.concept_type,
          requirement: r.requirement,
        })),
      });
      finish(extracted.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const onClose = (v: boolean) => {
    if (v) return onOpenChange(true);
    if (extracted) return finish(extracted.job_id);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-h-[calc(100svh-2rem)] gap-6 overflow-y-auto p-6 sm:max-w-[620px] sm:p-8">
        {!extracted ? (
          <form onSubmit={runExtraction} className="contents">
            <div className="pr-6">
              <DialogTitle className="mb-1.5 text-[22px] font-semibold tracking-tight">New job</DialogTitle>
              <DialogDescription className="text-sm">
                Paste a job posting. We'll pull out the requirements for you to review.
              </DialogDescription>
            </div>
            <Field label="Job title" htmlFor="job-title">
              <Input
                id="job-title"
                className="h-10"
                placeholder="e.g. Full-Stack Software Engineer"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                autoFocus
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Company" htmlFor="job-company">
                <Input
                  id="job-company"
                  className="h-10"
                  placeholder="e.g. Merkl"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                />
              </Field>
              <Field label="Location" htmlFor="job-location">
                <Input
                  id="job-location"
                  className="h-10"
                  placeholder="City, country or Remote"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </Field>
            </div>
            <Field label="Job description" htmlFor="job-description">
              <Textarea
                id="job-description"
                className="min-h-[200px] leading-relaxed"
                placeholder="Paste the full job description here"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2.5">
              <Button type="button" variant="outline" size="lg" className="px-4" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                size="lg"
                className="px-4"
                disabled={saving || !title.trim() || !description.trim()}
              >
                {saving ? <Loader2 className="animate-spin" /> : <Sparkles />}
                {saving ? "Extracting…" : "Extract requirements"}
              </Button>
            </div>
          </form>
        ) : (
          <>
            <div className="pr-6">
              <DialogTitle className="mb-1.5 text-[22px] font-semibold tracking-tight">Review requirements</DialogTitle>
              <DialogDescription className="text-sm">
                {edited.length} requirements found in the posting, each with its quote. The job is already saved — fix
                anything that looks wrong, or keep it as is.
              </DialogDescription>
            </div>
            <RequirementsEditor value={edited} onChange={setEdited} />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2.5">
              <Button variant="outline" size="lg" className="px-4" onClick={() => finish(extracted.job_id)}>
                Keep as is
              </Button>
              <Button size="lg" className="px-4" onClick={saveCorrected} disabled={saving}>
                {saving && <Loader2 className="animate-spin" />}
                {saving ? "Saving…" : "Save and view matches"}
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function JobCard({ job }: { job: JobRow }) {
  const place = jobPlace(job);
  return (
    <Link
      to="/jobs/$jobId"
      params={{ jobId: job.job_id }}
      className="group flex flex-col gap-5 rounded-[14px] bg-card p-6 ring-1 ring-border transition-shadow hover:shadow-lg hover:ring-border-strong focus-visible:outline-2 focus-visible:outline-ring"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1.5 text-lg leading-snug font-medium text-pretty">{job.title}</div>
          <div className="flex flex-wrap items-center gap-1.5 text-[13px] text-muted-foreground">
            <Building2 className="size-3.5" />
            {job.company || "—"}
            {place && (
              <>
                <span>·</span>
                {place}
              </>
            )}
          </div>
        </div>
        <ArrowUpRight className="size-[18px] shrink-0 text-primary transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <span className="rounded-md bg-muted px-2.5 py-0.5 text-[11px]">{job.required_count} required</span>
        <span className="rounded-md bg-muted px-2.5 py-0.5 text-[11px]">{job.nice_to_have_count} nice to have</span>
      </div>
      <div className="mt-auto h-px bg-gradient-to-r from-transparent via-border-strong to-transparent" />
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="text-[26px] font-medium tracking-tight tabular-nums">{fmt(job.matches_count)}</div>
          <div className="text-xs text-muted-foreground">matched talents</div>
        </div>
        {job.created_at && <div className="text-xs text-muted-foreground tabular-nums">Created {job.created_at}</div>}
      </div>
    </Link>
  );
}

export function JobsPage() {
  const { data, error, isLoading } = $api.useQuery("get", "/api/jobs", {}, { staleTime: 60_000 });
  const [dialog, setDialog] = useState(false);

  return (
    <div className="pt-4 pb-10 sm:pt-8">
      <JobsBackdrop />
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="mb-2 text-3xl font-semibold tracking-[-0.025em] sm:text-[40px]">Jobs</h1>
          <p className="text-[15px] text-muted-foreground">
            Paste a posting, and Talent Seed ranks talents by evidence for each requirement.
          </p>
        </div>
        <Button size="lg" className="h-10 px-4 text-sm" onClick={() => setDialog(true)}>
          <Plus /> New job
        </Button>
      </div>

      <div className="mt-10 grid gap-5 sm:grid-cols-[repeat(auto-fill,minmax(340px,1fr))]">
        {isLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-[230px] rounded-[14px]" />)}
        {data?.map((j) => (
          <JobCard key={j.job_id} job={j} />
        ))}
      </div>
      {error && (
        <EmptyState icon={Briefcase} title="Couldn't load jobs" error>
          Try reloading the page.
        </EmptyState>
      )}
      {!isLoading && !error && data?.length === 0 && (
        <EmptyState icon={Briefcase} title="No jobs yet">
          Paste your first posting to start matching.
        </EmptyState>
      )}
      <NewJobDialog open={dialog} onOpenChange={setDialog} />
    </div>
  );
}
