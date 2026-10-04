import { useState } from "react";
import { cn } from "@/lib/utils";

const initials = (name?: string | null) =>
  (name || "?")
    .replace(/[^\p{L}\p{N} ]/gu, "")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || "?";

/** GitHub avatar by numeric account id, falling back to initials. */
export function PersonAvatar({
  person,
  className,
}: {
  person: { display_name?: string | null; github_user_id?: number | null };
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <div
      aria-hidden
      className={cn(
        "relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full bg-accent-soft text-sm font-semibold text-primary",
        className,
      )}
    >
      {initials(person.display_name)}
      {person.github_user_id != null && !failed && (
        <img
          src={`https://avatars.githubusercontent.com/u/${person.github_user_id}?s=120&v=4`}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          className="absolute inset-0 size-full object-cover"
        />
      )}
    </div>
  );
}
