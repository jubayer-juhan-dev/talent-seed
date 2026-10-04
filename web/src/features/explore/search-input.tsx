import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useExplore } from "./use-explore";

export const SEARCH_INPUT_ID = "explore-search";

/** Debounced search box. "/" anywhere focuses it (wired in AppShell). */
export function SearchInput() {
  const { search, update } = useExplore();
  const [text, setText] = useState(search.q ?? "");
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Follow outside changes (chip removed, back button) unless the user is typing.
  useEffect(() => {
    if (document.activeElement?.id !== SEARCH_INPUT_ID) setText(search.q ?? "");
  }, [search.q]);

  const change = (v: string) => {
    setText(v);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => update({ q: v.trim() || undefined }), 300);
  };

  return (
    <label
      data-tour="search"
      className="flex h-9 min-w-0 flex-[1_1_280px] items-center gap-2 rounded-lg border bg-card px-3 shadow-xs transition-[border-color,box-shadow] focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/25"
    >
      <Search className="size-4 shrink-0 text-faint" />
      <input
        id={SEARCH_INPUT_ID}
        type="search"
        value={text}
        onChange={(e) => change(e.target.value)}
        onKeyDown={(e) => {
          if (e.key !== "Escape") return;
          e.currentTarget.blur();
          if (text) change("");
        }}
        placeholder="Search name, GitHub login, exact email or gh:… id"
        autoComplete="off"
        aria-label="Search people"
        className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-faint [&::-webkit-search-cancel-button]:hidden"
      />
      {text ? (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => change("")}
          className="text-faint hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      ) : (
        <kbd className="rounded-[5px] border border-b-2 bg-muted px-1.5 font-mono text-[11px] text-muted-foreground">
          /
        </kbd>
      )}
    </label>
  );
}
