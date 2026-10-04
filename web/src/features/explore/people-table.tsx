import { type ColumnDef, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { PersonRow } from "@/api/client";
import { AiBadge } from "@/components/app/ai-badge";
import { CohortBadge } from "@/components/app/cohort-badge";
import { PersonAvatar } from "@/components/app/person-avatar";
import { StarButton } from "@/components/app/star-button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { day, fmt, label } from "@/lib/format";
import { cn } from "@/lib/utils";
import { activeShare, ChainsLine, GithubLine } from "./person-card";
import { DEFAULTS, dirOf, SORTS, type SortKey } from "./search";
import { useExplore } from "./use-explore";

type Col = ColumnDef<PersonRow> & { meta?: { sort?: SortKey; align?: "right" } };

const columns: Col[] = [
  { id: "star", header: "", cell: ({ row }) => <StarButton person={row.original} /> },
  {
    id: "name",
    header: "Person",
    meta: { sort: "name" },
    cell: ({ row: { original: p } }) => (
      <div className="flex items-center gap-2.5">
        <PersonAvatar person={p} className="size-[30px] text-xs" />
        <div className="min-w-0">
          <div className="max-w-[220px] truncate font-medium">{p.display_name || "(no name)"}</div>
          <div className="flex max-w-[220px] text-xs text-muted-foreground">
            <GithubLine p={p} />
          </div>
        </div>
      </div>
    ),
  },
  {
    id: "cohort",
    header: "Cohort",
    cell: ({ row: { original: p } }) => (
      <Tooltip>
        <TooltipTrigger>
          <CohortBadge cohort={p.priority_cohort} />
        </TooltipTrigger>
        <TooltipContent>{p.priority_cohort_reason}</TooltipContent>
      </Tooltip>
    ),
  },
  {
    id: "ai",
    header: "AI",
    cell: ({ row }) =>
      row.original.ai_enriched ? <AiBadge person={row.original} compact /> : <span className="text-faint">–</span>,
  },
  {
    id: "active",
    header: "Active days (84)",
    meta: { sort: "active_days" },
    cell: ({ row: { original: p } }) => (
      <span className="flex items-center gap-2">
        <span className="inline-block h-1.5 w-16 overflow-hidden rounded-full bg-bar-track">
          <span className="block h-full rounded-full bg-bar-strong" style={{ width: `${activeShare(p)}%` }} />
        </span>
        <span className="tabular-nums">{fmt(p.active_days_in_window)}</span>
      </span>
    ),
  },
  {
    id: "segments",
    header: "Segments",
    cell: ({ row: { original: p } }) => (
      <span className="text-muted-foreground">
        {label(p.activity_segment)} · {label(p.tenure_segment)}
      </span>
    ),
  },
  {
    id: "chains",
    header: "Chains",
    meta: { sort: "ecosystems" },
    cell: ({ row: { original: p } }) => (
      <span className="block max-w-[240px] truncate">
        <ChainsLine p={p} />
      </span>
    ),
  },
  { id: "country", header: "Country", cell: ({ row }) => row.original.country || "–" },
  {
    id: "last",
    header: "Last active",
    meta: { sort: "last_activity" },
    cell: ({ row }) => <span className="tabular-nums">{day(row.original.last_activity_date)}</span>,
  },
  {
    id: "commits",
    header: "Commits",
    meta: { sort: "commits", align: "right" },
    cell: ({ row }) => <span className="tabular-nums">{fmt(row.original.commit_count)}</span>,
  },
];

export function PeopleTable({ rows, onOpen }: { rows: PersonRow[]; onOpen: (id: string) => void }) {
  const { search, update } = useExplore();
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (r) => r.person_id,
  });
  const sort = search.sort ?? DEFAULTS.sort;
  const dir = dirOf(search);

  const sortBy = (key: SortKey) => {
    const natural = SORTS.find((s) => s.key === key)?.dir ?? "desc";
    const nextDir = key === sort ? (dir === "desc" ? "asc" : "desc") : natural;
    update({ sort: key === DEFAULTS.sort ? undefined : key, dir: nextDir === natural ? undefined : nextDir });
  };

  return (
    <div className="overflow-x-auto rounded-xl border bg-card shadow-xs">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          {table.getHeaderGroups().map((g) => (
            <tr key={g.id}>
              {g.headers.map((h) => {
                const meta = (h.column.columnDef as Col).meta;
                const active = meta?.sort === sort;
                return (
                  <th
                    key={h.id}
                    aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : undefined}
                    className={cn(
                      "border-b bg-muted px-3 py-2.5 text-left text-xs font-semibold whitespace-nowrap text-muted-foreground",
                      meta?.align === "right" && "text-right",
                    )}
                  >
                    {meta?.sort ? (
                      <button
                        type="button"
                        onClick={() => sortBy(meta.sort as SortKey)}
                        className="hover:text-foreground"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {active && <span className="text-primary"> {dir === "desc" ? "↓" : "↑"}</span>}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((r) => (
            <tr
              key={r.id}
              tabIndex={0}
              onClick={() => onOpen(r.id)}
              onKeyDown={(e) => e.key === "Enter" && onOpen(r.id)}
              className="cursor-pointer transition-colors last:[&>td]:border-0 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
            >
              {r.getVisibleCells().map((c) => (
                <td
                  key={c.id}
                  className={cn(
                    "border-b px-3 py-2.5 whitespace-nowrap",
                    (c.column.columnDef as Col).meta?.align === "right" && "text-right",
                  )}
                >
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
