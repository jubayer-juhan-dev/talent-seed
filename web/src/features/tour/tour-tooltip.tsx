import { X } from "lucide-react";
import type { TooltipRenderProps } from "react-joyride";
import { Button } from "@/components/ui/button";

/** Tour tooltip built from the app's own components, so it follows the theme. */
export function TourTooltip({
  step,
  index,
  size,
  isLastStep,
  backProps,
  primaryProps,
  skipProps,
  tooltipProps,
}: TooltipRenderProps) {
  return (
    <div
      {...tooltipProps}
      className="w-[min(360px,calc(100vw-24px))] animate-in rounded-2xl border bg-popover p-[18px] text-popover-foreground shadow-xl fade-in zoom-in-95 duration-150"
    >
      <div className="mb-1.5 flex items-start justify-between gap-3">
        {step.title && <h3 className="text-[15.5px] font-bold tracking-tight">{step.title}</h3>}
        <button
          type="button"
          {...skipProps}
          aria-label="Close the tour"
          title="Close the tour"
          className="-mt-1 -mr-1 grid size-7 shrink-0 place-items-center rounded-md text-faint hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="text-[13.5px] leading-relaxed text-muted-foreground [&_p+p]:mt-2">{step.content}</div>
      <div className="mt-4 flex items-center gap-2">
        <span className="mr-auto text-xs text-faint tabular-nums">
          {index + 1} of {size}
        </span>
        {index > 0 && (
          <Button variant="ghost" size="sm" {...backProps}>
            Back
          </Button>
        )}
        <Button size="sm" {...primaryProps}>
          {isLastStep ? "Done" : "Next"}
        </Button>
      </div>
    </div>
  );
}
