import { keepPreviousData } from "@tanstack/react-query";
import {
  Activity,
  Blocks,
  Check,
  ChevronLeft,
  ChevronRight,
  GitMerge,
  Hourglass,
  ListFilter as ListFilterIcon,
  MapPin,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { $api } from "@/api/client";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { fmt, label } from "@/lib/format";
import { cn } from "@/lib/utils";
import { joinList, type ListFilter, listOf } from "./search";
import { useExplore } from "./use-explore";

export const FILTERS: Record<ListFilter, { title: string; icon: typeof Activity; hint: string; options?: string[] }> = {
  eco: { title: "Chain or project", icon: Blocks, hint: "Ethereum, Solana, Uniswap, Anza…" },
  activity: {
    title: "Activity",
    icon: Activity,
    hint: "How often they commit (last 84 days)",
    options: ["FULL_TIME", "PART_TIME", "ONE_TIME", "UNKNOWN"],
  },
  tenure: {
    title: "Tenure",
    icon: Hourglass,
    hint: "Time since first original crypto commit",
    options: ["ESTABLISHED", "EMERGING", "NEWCOMER", "UNKNOWN"],
  },
  exclusivity: {
    title: "Exclusivity",
    icon: GitMerge,
    hint: "One chain or several. Unknown = not applicable",
    options: ["EXCLUSIVE", "MULTICHAIN", "UNKNOWN"],
  },
  country: { title: "Country", icon: MapPin, hint: "Where known" },
};

/** "Filter" button: a menu of filter types, each opening a checklist. Chains/projects are searched on the server. */
export function FilterMenu() {
  const [open, setOpen] = useState(false);
  const [panel, setPanel] = useState<ListFilter | null>(null);
  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setPanel(null);
      }}
    >
      <PopoverTrigger asChild>
        <Button variant="outline" className="gap-2">
          <ListFilterIcon className="size-4" />
          Filter
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-[min(340px,calc(100vw-24px))] p-0">
        {panel ? <Panel filter={panel} onBack={() => setPanel(null)} /> : <Root onPick={setPanel} />}
      </PopoverContent>
    </Popover>
  );
}

function Root({ onPick }: { onPick: (f: ListFilter) => void }) {
  const { search } = useExplore();
  return (
    <Command>
      <CommandList>
        <CommandGroup heading="Add a filter">
          {(Object.keys(FILTERS) as ListFilter[]).map((k) => {
            const f = FILTERS[k];
            const n = listOf(search, k).length;
            return (
              <CommandItem key={k} value={f.title} onSelect={() => onPick(k)} className="gap-3 py-2">
                <f.icon className="size-4 text-muted-foreground" />
                <div className="flex-1">
                  <div className="font-medium">{f.title}</div>
                  <div className="text-xs text-muted-foreground">{f.hint}</div>
                </div>
                {n ? (
                  <span className="grid h-[18px] min-w-[18px] place-items-center rounded-full bg-primary px-1.5 text-[11px] font-bold text-primary-foreground">
                    {n}
                  </span>
                ) : (
                  <ChevronRight className="size-4 text-faint" />
                )}
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </Command>
  );
}

type Option = { value: string; label: string; hint?: string; n?: number };

function Panel({ filter, onBack }: { filter: ListFilter; onBack: () => void }) {
  const { search, update } = useExplore();
  const selected = listOf(search, filter);
  const toggle = (v: string) =>
    update({ [filter]: joinList(filter, selected.includes(v) ? selected.filter((x) => x !== v) : [...selected, v]) });
  const f = FILTERS[filter];

  const header = (
    <>
      <button
        type="button"
        onClick={onBack}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-sm font-semibold hover:bg-muted"
      >
        <ChevronLeft className="size-4" />
        {f.title}
      </button>
      <CommandSeparator />
    </>
  );

  if (filter === "eco") return <EcoPanel header={header} selected={selected} toggle={toggle} />;
  if (filter === "country") return <CountryPanel header={header} selected={selected} toggle={toggle} />;
  return (
    <Command>
      {header}
      <CommandList>
        <OptionItems
          options={(f.options ?? []).map((v) => ({ value: v, label: label(v) }))}
          selected={selected}
          toggle={toggle}
        />
      </CommandList>
      {filter === "exclusivity" && (
        <p className="px-3 pt-1 pb-3 text-xs text-muted-foreground">
          Unknown means no chain-mapped work in the window, so exclusivity doesn't apply.
        </p>
      )}
    </Command>
  );
}

function OptionItems({
  options,
  selected,
  toggle,
}: {
  options: Option[];
  selected: string[];
  toggle: (v: string) => void;
}) {
  return (
    <CommandGroup>
      {options.map((o) => {
        const on = selected.includes(o.value);
        return (
          <CommandItem
            key={o.value}
            value={o.value}
            onSelect={() => toggle(o.value)}
            className="gap-3"
            aria-checked={on}
          >
            <span
              className={cn(
                "grid size-4 shrink-0 place-items-center rounded-[5px] border-[1.5px] border-border-strong transition-colors",
                on && "border-primary bg-primary text-primary-foreground",
              )}
            >
              {on && <Check className="size-3 stroke-3 text-primary-foreground" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate">{o.label}</div>
              {o.hint && <div className="text-xs text-muted-foreground">{o.hint}</div>}
            </div>
            {o.n != null && <span className="text-xs text-faint tabular-nums">{fmt(o.n)}</span>}
          </CommandItem>
        );
      })}
    </CommandGroup>
  );
}

function CountryPanel({
  header,
  selected,
  toggle,
}: {
  header: ReactNode;
  selected: string[];
  toggle: (v: string) => void;
}) {
  const { data } = $api.useQuery("get", "/api/meta", {}, { staleTime: Infinity });
  const options = (data?.countries ?? []).map((c) => ({ value: c.k, label: c.k, n: c.n }));
  return (
    <Command>
      {header}
      <CommandInput placeholder="Search countries" autoFocus />
      <CommandList className="max-h-[300px]">
        <CommandEmpty>No matches.</CommandEmpty>
        <OptionItems options={options} selected={selected} toggle={toggle} />
      </CommandList>
    </Command>
  );
}

function EcoPanel({
  header,
  selected,
  toggle,
}: {
  header: ReactNode;
  selected: string[];
  toggle: (v: string) => void;
}) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 200);
    return () => clearTimeout(t);
  }, [text]);
  const { data, isFetching, error } = $api.useQuery(
    "get",
    "/api/ecosystems",
    { params: { query: { q } } },
    { placeholderData: keepPreviousData, staleTime: 5 * 60_000 },
  );
  const hits: Option[] = (data?.rows ?? []).map((r) => ({
    value: r.k,
    label: r.k,
    n: r.n,
    hint: r.level === "TOP_LEVEL" ? "Chain" : "Project",
  }));
  // Selected names stay visible (and removable) even when the current search doesn't return them.
  const pinned = selected
    .filter((v) => !hits.some((h) => h.value === v))
    .map((v) => ({ value: v, label: v, hint: "Selected" }));
  return (
    <Command shouldFilter={false}>
      {header}
      <CommandInput value={text} onValueChange={setText} placeholder="Search 7,000 chains and projects" autoFocus />
      <CommandList className="max-h-[320px]">
        {error ? (
          <p className="px-3 py-4 text-sm text-destructive">Couldn't search ecosystems.</p>
        ) : (
          <>
            {!isFetching && hits.length === 0 && pinned.length === 0 && (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">No matches.</p>
            )}
            {pinned.length > 0 && <OptionItems options={pinned} selected={selected} toggle={toggle} />}
            <OptionItems options={hits} selected={selected} toggle={toggle} />
          </>
        )}
      </CommandList>
      <p className="border-t px-3 py-2 text-[11.5px] text-faint">Counts are active P1–P3 developers.</p>
    </Command>
  );
}
