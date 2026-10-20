import { Link } from "@tanstack/react-router";
import { ArrowLeft } from "lucide-react";
import { $api } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RequirementsList } from "./requirements";

function stateBadge(state: string) {
  if (state === "covered") return <Badge className="bg-green-600">✓ covered</Badge>;
  if (state === "partial") return <Badge className="bg-amber-500">~ partial</Badge>;
  return <Badge variant="destructive">✗ missing</Badge>;
}

export function JobDetailPage({ jobId }: { jobId: string }) {
  const job = $api.useQuery("get", "/api/jobs/{job_id}", {
    params: { path: { job_id: jobId } },
  });
  const matches = $api.useQuery(
    "get",
    "/api/jobs/{job_id}/matches",
    { params: { path: { job_id: jobId } } },
    { staleTime: 60_000 },
  );

  return (
    <div className="space-y-4">
      <Link to="/jobs" className="inline-flex items-center gap-1 text-sm text-muted-foreground">
        <ArrowLeft className="size-4" /> All jobs
      </Link>
      {job.isLoading && <Skeleton className="h-40 w-full" />}
      {job.data && (
        <Card>
          <CardHeader>
            <CardTitle>{job.data.title}</CardTitle>
            <p className="text-sm text-muted-foreground">
              {[job.data.company, job.data.location_country ?? job.data.location_text].filter(Boolean).join(" · ")}
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <RequirementsList requirements={job.data.requirements} />
            <details className="text-sm">
              <summary className="cursor-pointer text-muted-foreground">Full description</summary>
              <pre className="mt-2 whitespace-pre-wrap text-sm">{job.data.description}</pre>
            </details>
          </CardContent>
        </Card>
      )}

      <h2 className="text-lg font-semibold">Matches</h2>
      {matches.data && (
        <p className="text-sm text-muted-foreground">
          {matches.data.total} talents matched out of {matches.data.pool} with evidence
          {matches.data.total > matches.data.items.length ? ` — showing top ${matches.data.items.length}` : ""}
        </p>
      )}
      {matches.isLoading && <Skeleton className="h-40 w-full" />}
      <div className="space-y-2">
        {matches.data?.items.map((m) => (
          <Card key={m.talent_id}>
            <CardContent className="flex flex-col gap-2 pt-4">
              <div className="flex items-center gap-3">
                <Link to="/explore" search={{ p: m.talent_id }} className="font-medium hover:underline">
                  {m.name ?? m.talent_id}
                </Link>
                {m.github_login && <span className="text-sm text-muted-foreground">@{m.github_login}</span>}
                <span className="ml-auto flex items-center gap-2">
                  <span className="h-2 w-28 overflow-hidden rounded bg-muted">
                    <span className="block h-full bg-primary" style={{ width: `${Math.round(m.score * 100)}%` }} />
                  </span>
                  <b>{Math.round(m.score * 100)}%</b>
                  {m.contributor_concepts > 0 && (
                    <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-[11px] font-medium text-emerald-600">
                      Contributor ×{m.contributor_concepts}
                    </span>
                  )}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {m.breakdown.map((b) => (
                  <span
                    key={`${b.concept_id}-${b.requirement}`}
                    className="inline-flex items-center gap-1"
                    title={
                      b.evidence_status
                        ? `${b.evidence_status}${b.usage_level ? ` · ${b.usage_level.replace("_USAGE", "")}` : ""}${b.confidence ? ` (${Math.round(b.confidence * 100)}%)` : ""}`
                        : "no evidence"
                    }
                  >
                    {stateBadge(b.state)}
                    <span className="text-xs">{b.concept_name}</span>
                  </span>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
        {matches.data?.total === 0 && <p className="text-sm text-muted-foreground">No talent matches this job yet.</p>}
      </div>
    </div>
  );
}
