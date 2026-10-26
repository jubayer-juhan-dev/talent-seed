import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  children,
  error,
  className,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  error?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-2.5 px-5 py-14 text-center text-muted-foreground", className)}>
      <div
        className={cn(
          "grid size-12 place-items-center rounded-[14px] bg-background text-faint elev-sm",
          error && "bg-destructive/10 text-destructive",
        )}
      >
        <Icon className="size-[22px]" />
      </div>
      <h3 className="text-[15px] font-medium text-foreground">{title}</h3>
      {children && <div className="max-w-md">{children}</div>}
    </div>
  );
}
