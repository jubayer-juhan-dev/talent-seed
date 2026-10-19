import { AtSign, Building2, CalendarDays, Globe, Mail, MapPin, Share2, UserCheck, Users } from "lucide-react";
import { $api } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

function Row({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 border-b px-3.5 py-2.5 last:border-0">
      <span className="mt-0.5 shrink-0 text-faint">{icon}</span>
      <span className="w-28 shrink-0 text-xs text-faint">{label}</span>
      <span className="min-w-0 flex-1 text-sm break-words">{children}</span>
    </div>
  );
}

function Link({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline">
      {children}
    </a>
  );
}

/** GitHub profile details (Tier-1 harvest cache) for the Contact tab. */
export function GithubProfileSection({ id }: { id: string }) {
  const { data, error, isPending } = $api.useQuery("get", "/api/person/github-profile", {
    params: { query: { id } },
  });
  if (isPending)
    return (
      <section>
        <Skeleton className="h-40" />
      </section>
    );
  if (error || !data) return null;
  if (data.deleted)
    return (
      <div className="overflow-hidden rounded-xl border bg-card">
        <EmptyState icon={Users} title="GitHub account deleted">
          This GitHub account no longer exists (404 on the GitHub API).
        </EmptyState>
      </div>
    );

  const rows: React.ReactNode[] = [];
  if (data.name)
    rows.push(
      <Row key="name" icon={<Users className="size-4" />} label="Name">
        {data.name}
      </Row>,
    );
  if (data.bio)
    rows.push(
      <Row key="bio" icon={<Users className="size-4" />} label="Bio">
        {data.bio}
      </Row>,
    );
  if (data.company)
    rows.push(
      <Row key="company" icon={<Building2 className="size-4" />} label="Company">
        {data.company}
      </Row>,
    );
  if (data.location)
    rows.push(
      <Row key="location" icon={<MapPin className="size-4" />} label="Location">
        {data.location}
      </Row>,
    );
  if (data.website)
    rows.push(
      <Row key="website" icon={<Globe className="size-4" />} label="Website">
        <Link href={data.website.startsWith("http") ? data.website : `https://${data.website}`}>{data.website}</Link>
      </Row>,
    );
  if (data.x_url)
    rows.push(
      <Row key="x" icon={<AtSign className="size-4" />} label="X (Twitter)">
        <Link href={data.x_url}>{data.x_handle}</Link>
      </Row>,
    );
  if (data.linkedin_url)
    rows.push(
      <Row key="linkedin" icon={<Share2 className="size-4" />} label="LinkedIn">
        <Link href={data.linkedin_url}>{data.linkedin_url.replace(/^https?:\/\//, "")}</Link>
      </Row>,
    );
  if (data.public_email)
    rows.push(
      <Row key="email" icon={<Mail className="size-4" />} label="Public email">
        <span className="font-mono text-[13px]">{data.public_email}</span>{" "}
        <span className="text-xs text-faint">(unverified)</span>
      </Row>,
    );
  if (data.hireable != null)
    rows.push(
      <Row key="hireable" icon={<UserCheck className="size-4" />} label="Hireable">
        {data.hireable ? "Yes" : "No"}
      </Row>,
    );
  if (data.followers != null)
    rows.push(
      <Row key="followers" icon={<Users className="size-4" />} label="Followers">
        {data.followers.toLocaleString()}
      </Row>,
    );
  if (data.account_created)
    rows.push(
      <Row key="created" icon={<CalendarDays className="size-4" />} label="On GitHub since">
        {data.account_created}
      </Row>,
    );

  if (!rows.length) return null;
  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="border-b bg-muted/40 px-3.5 py-2 text-xs font-semibold tracking-wider text-faint uppercase">
        GitHub profile · @{data.login}
      </div>
      {rows}
    </div>
  );
}
