import { Link } from "@tanstack/react-router";
import { Briefcase } from "lucide-react";
import { useState } from "react";
import { $api, fetchClient, type Schemas } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { type JobRequirement, RequirementsEditor } from "./requirements";

type JobDetail = Schemas["JobDetail"];

function NewJobDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const [extracted, setExtracted] = useState<JobDetail | null>(null);
  const [edited, setEdited] = useState<JobRequirement[]>([]);
  const [step, setStep] = useState<"paste" | "review">("paste");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const runExtraction = async () => {
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
      setStep("review");
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
      setStep("paste");
      setExtracted(null);
      setDescription("");
      setTitle("");
      onOpenChange(false);
      window.location.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const close = () => {
    if (step === "review") {
      setStep("paste"); // job already saved by extraction; edits optional
      setExtracted(null);
      onOpenChange(false);
      window.location.reload();
      return;
    }
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? onOpenChange(v) : close())}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{step === "paste" ? "New job — paste posting" : "Review extracted requirements"}</DialogTitle>
        </DialogHeader>
        {step === "paste" ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Input placeholder="Job title" value={title} onChange={(e) => setTitle(e.target.value)} />
              <Input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
              <Input
                placeholder="Location (city, Remote)"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
              />
            </div>
            <Textarea
              placeholder="Paste the full job description here…"
              rows={12}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={runExtraction} disabled={saving || !title.trim() || !description.trim()}>
                {saving ? "Extracting…" : "Extract requirements"}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Luna extracted {edited.length} requirements with evidence quotes. Fix anything — or skip, the list is
              already saved.
            </p>
            <RequirementsEditor value={edited} onChange={setEdited} />
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={close}>
                Done (keep as-is)
              </Button>
              <Button onClick={saveCorrected} disabled={saving}>
                {saving ? "Saving…" : "Save corrections"}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function JobsPage() {
  const { data, error, isLoading } = $api.useQuery("get", "/api/jobs", {}, { staleTime: 60_000 });
  const [dialog, setDialog] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Jobs</h1>
        <Button onClick={() => setDialog(true)}>
          <Briefcase className="mr-1.5 size-4" /> New job
        </Button>
      </div>
      {isLoading && <Skeleton className="h-24 w-full" />}
      {error && <p className="text-sm text-destructive">Failed to load jobs.</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((j) => (
          <Link key={j.job_id} to="/jobs/$jobId" params={{ jobId: j.job_id }}>
            <Card className="h-full transition-colors hover:border-primary/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{j.title}</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {[j.company, j.location_country ?? j.location_text].filter(Boolean).join(" · ")}
                </p>
              </CardHeader>
              <CardContent className="flex items-center gap-2">
                <Badge variant="secondary">{j.requirements_count} requirements</Badge>
                <Badge variant="outline">{j.source}</Badge>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
      {!isLoading && !error && data?.length === 0 && (
        <p className="text-sm text-muted-foreground">No jobs yet. Paste your first posting to start matching.</p>
      )}
      <NewJobDialog open={dialog} onOpenChange={setDialog} />
    </div>
  );
}
