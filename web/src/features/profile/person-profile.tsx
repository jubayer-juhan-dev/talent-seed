import { UserX } from "lucide-react";
import { useEffect } from "react";
import { $api, errorText } from "@/api/client";
import { EmptyState } from "@/components/app/empty-state";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { useMedia } from "@/hooks/use-media";
import { ProfileBody } from "./profile-body";

/** The person profile: a dialog on desktop, a bottom sheet on phones. `ids` is the list ←/→ step through. */
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

  const body = id ? <Loader id={id} prev={prev} next={next} onNavigate={onNavigate} onClose={onClose} /> : null;
  const a11y = (Title: typeof DialogTitle, Desc: typeof DialogDescription) => (
    <>
      <Title className="sr-only">Person profile</Title>
      <Desc className="sr-only">Who this developer is, why they are in their cohort, and how to reach them.</Desc>
    </>
  );

  if (desktop)
    return (
      <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
        <DialogContent
          showCloseButton={false}
          className="flex max-h-[90vh] flex-col gap-0 overflow-hidden bg-background p-0 sm:max-w-[880px]"
        >
          {a11y(DialogTitle, DialogDescription)}
          {body}
        </DialogContent>
      </Dialog>
    );
  return (
    <Sheet open={!!id} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side="bottom"
        showCloseButton={false}
        className="max-h-[92vh] gap-0 rounded-t-2xl bg-background p-0"
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
  onNavigate: (id: string) => void;
  onClose: () => void;
}) {
  const { data, error, isPending } = $api.useQuery("get", "/api/person", { params: { query: { id: props.id } } });
  if (isPending)
    return (
      <div className="flex flex-col gap-4 p-5">
        <div className="flex gap-4">
          <Skeleton className="size-[60px] rounded-full" />
          <div className="flex-1 space-y-2.5 pt-1">
            <Skeleton className="h-5 w-1/2" />
            <Skeleton className="h-3.5 w-1/3" />
          </div>
        </div>
        <Skeleton className="h-[72px]" />
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-[84px]" />
          ))}
        </div>
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
