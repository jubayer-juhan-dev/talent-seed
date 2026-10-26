import { UserX } from "lucide-react";
import { useEffect } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useMedia } from "@/hooks/use-media";
import { ProfileBody } from "./profile-body";

/** The person profile: a drawer from the right on desktop, a bottom sheet on phones. `ids` is the list ←/→ step through. */
export function PersonProfile({
  id,
  ids,
  onNavigate,
  onClose,
}: {
  id: string | undefined;
  ids: string[];
  onNavigate: (id: string) => void;
  onClose: () => void;
}) {
  const desktop = useMedia("(min-width: 640px)");
  const index = id ? ids.indexOf(id) : -1;
  const prev = index > 0 ? ids[index - 1] : undefined;
  const next = index >= 0 && index < ids.length - 1 ? ids[index + 1] : undefined;

  useEffect(() => {
    if (!id) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest("input, textarea, [role=menu], [role=listbox]")) return;
      if (e.key === "ArrowLeft" && prev) onNavigate(prev);
      if (e.key === "ArrowRight" && next) onNavigate(next);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id, prev, next, onNavigate]);

  const pos =
    index >= 0 ? `${(index + 1).toLocaleString("en-US")} of ${ids.length.toLocaleString("en-US")}` : undefined;
  const body = id ? (
    <Loader id={id} prev={prev} next={next} pos={pos} onNavigate={onNavigate} onClose={onClose} />
  ) : null;
  const a11y = (Title: typeof SheetTitle, Desc: typeof SheetDescription) => (
    <>
      <Title className="sr-only">Person profile</Title>
      <Desc className="sr-only">Who this developer is, why they are in their cohort, and how to reach them.</Desc>
    </>
  );

  if (desktop)
    return (
      <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
        <SheetContent
          side="right"
          showCloseButton={false}
          overlayClassName="bg-background/60 supports-backdrop-filter:backdrop-blur-[3px]"
          className="w-full gap-0 border-l border-divider bg-card p-0 shadow-[var(--elev-lg)] outline-none data-[side=right]:w-[min(600px,100%)] data-[side=right]:sm:max-w-[600px]"
        >
          {a11y(SheetTitle, SheetDescription)}
          {body}
        </SheetContent>
      </Sheet>
    );
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="max-h-[92vh] gap-0 rounded-t-[14px] border-divider bg-card p-0"
      >
        <div className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-border-strong" />
        {a11y(SheetTitle, SheetDescription)}
        {body}
      </SheetContent>
    </Sheet>
  );
}

function Loader(props: {
  id: string;
  prev?: string;
  next?: string;
  pos?: string;
  onNavigate: (id: string) => void;
  onClose: () => void;
}) {
  const { data, error, isPending } = $api.useQuery("get", "/api/person", { params: { query: { id: props.id } } });
  if (isPending)
    return (
      <div className="flex flex-col gap-5 px-5 pt-[68px] sm:px-7">
        <div className="flex gap-4">
          <Skeleton className="size-14 rounded-full" />
          <div className="flex-1 space-y-2.5 pt-1">
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-3.5 w-1/3" />
          </div>
        </div>
        <Skeleton className="mt-12 h-px" />
        <div className="grid grid-cols-2 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[96px] rounded-lg" />
          ))}
        </div>
        <Skeleton className="h-[76px] rounded-lg" />
        <Skeleton className="h-44" />
      </div>
    );
  if (error || !data)
    return (
      <EmptyState icon={UserX} title="Couldn't load this person" error>
        {errorText(error)}
      </EmptyState>
    );
  return <ProfileBody d={data} {...props} />;
}
