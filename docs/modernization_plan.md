# Talent Seed viewer: move to a modern stack (React + TypeScript + Vite, FastAPI)

## Context
The seed viewer works and is live (Cloudflare link, systemd), but it is one 1,289-line hand-written
`index.html` (vanilla JS, template strings, CSS in one `<style>`) plus a 339-line stdlib `http.server`
backend. It has grown past what that format handles well: no types, no components, everything
re-rendered by string concatenation, hard for anyone else to work on. The user wants to keep
developing it with a modern design and modern tools.

Goal: rebuild the frontend in React + TypeScript with a component library, and put the API on
FastAPI with typed models, **without changing what the app does or how it's hosted**. Same data,
same features, same link, same read-only rules. The live app keeps working throughout.

Constraints that stay (from `docs/handoff_seed_viewer_design.md`):
- DuckDB opened read-only, one connection per request; never write to it.
- No new running services (no Postgres, no separate Node server). Node is used **only at build
  time**; the server ships static files.
- Bind to 127.0.0.1; keep the access-key gate; keep "unverified email", "draft cohort",
  snapshot date and the Electric Capital CC BY 4.0 attribution visible.
- `scripts/m4_build_talent_seed.py` untouched.

## Target architecture
```
Browser ── Cloudflare tunnel ── FastAPI (uvicorn, 127.0.0.1:8765, systemd "talent-seed-viewer")
                                   ├─ /api/*      typed JSON endpoints (same URLs as today)
                                   ├─ /api/export.csv
                                   └─ /           static React build (web/dist)
                                        │
                                   DuckDB data/talent_seed.duckdb (read-only)
                                   SQLite data/github_logins.sqlite (read-only overlay)
```

## Stack
| Layer | Choice |
|---|---|
| Frontend | React 19 + TypeScript, Vite |
| UI | Tailwind CSS v4 + shadcn/ui (Radix: Dialog, Sheet, Popover, Command, Tabs, Tooltip, Sonner toasts) |
| Server state | TanStack Query |
| Routing + URL filters | TanStack Router (typed search params → shareable views, as today) |
| Table | TanStack Table (+ Virtual if needed) |
| Charts | shadcn charts (Recharts) |
| Icons / motion / tour | lucide-react, Motion, react-joyride |
| API types | FastAPI Pydantic models → OpenAPI → `openapi-typescript` → typed client |
| Backend | FastAPI + uvicorn, duckdb, sqlite3 (stdlib) |
| Tooling | pnpm, Biome, Vitest, Playwright, GitHub Actions |

## Repo layout (same repo)
```
scripts/seed_viewer/        current app (kept until switch-over, then removed)
viewer_api/                 FastAPI app
  main.py  queries.py  models.py  auth.py  logins.py
web/                        React app
  src/routes/ (overview, explore)  src/components/ (person-modal, filters, charts, shortlist…)
  src/api/ (generated types + client)  src/lib/ (format, labels, cohort rules)
```

## Steps

### Step 1 — FastAPI backend (frontend unchanged)
- Move logic from `scripts/seed_viewer/server.py` into `viewer_api/`, reusing as-is:
  `build_filters`, `api_people`, `api_overview`, `api_ecosystems`, `export_csv`, `api_person`,
  `api_meta`, `add_logins`/`looked_up` (GitHub-login overlay), `jsonable`.
- Same URLs and JSON shapes, so the current `index.html` keeps working unmodified.
- Pydantic response models for every endpoint; `/api/openapi.json` and `/api/docs`.
- Access key as a FastAPI dependency (`?key=`, `X-Access-Key`, cookie — same rules as today).
- Read-only DuckDB per request via a dependency that opens and closes the connection; a 503 when
  the database is being rebuilt (current behaviour).
- Add `fastapi`, `uvicorn` to `pyproject.toml`; switch the systemd unit's ExecStart to uvicorn.
- Check: curl every endpoint old vs new and diff the JSON; the live page works unchanged.

### Step 2 — Frontend scaffold and design system
- `web/`: Vite + React + TS, Tailwind, shadcn/ui init, Biome, Vitest.
- Design tokens copied from today's CSS variables (light/dark, cohort colours P1/P2/P3/HOLD,
  chart ramp validated earlier) into Tailwind theme; Inter + JetBrains Mono.
- Generated API types (`pnpm gen:api`), typed fetch client that sends `X-Access-Key`
  (port of `api()` + `ACCESS_KEY` logic in `index.html`).
- App shell: top bar (brand, Overview/Explore tabs, Draft data-notes popover, theme toggle,
  shortlist button, tour button), footer with attribution.
- Vite dev server proxies `/api` to FastAPI for local development.

### Step 3 — Explore screen
- Cohort segmented control, search (`/` shortcut), filter popover with Command search
  (chain/project type-ahead, activity, tenure, exclusivity, country), removable chips,
  hide-bots switch, sort menu, cards/table toggle, "Load more" (TanStack infinite query),
  skeletons and empty/error states.
- All filters in typed URL search params (same param names as today so old links keep working).

### Step 4 — Person profile
- shadcn Dialog on desktop, Sheet (bottom) on mobile; `#p=` deep link → route param.
- Header (avatar, login with source tooltip, location, confidence), "Why P1" callout, flags,
  stats, tabs: Overview (chains, projects, top original repos), Contact (unverified emails,
  copy), Repos, Data details. ←/→ navigation, star.

### Step 5 — Overview screen
- Cohort cards (count-up), chain stacked bars (P1 vs P2–P3) with tooltips and legend,
  tenure × activity heatmap, top countries, "How to read this data". Clicks jump into Explore.

### Step 6 — Shortlist, export, tour
- Shortlist in localStorage (same key `ts.shortlist`, so existing shortlists carry over), drawer.
- Export dialog with caveats → `/api/export.csv` (filter or shortlist ids).
- react-joyride tour with the same 12 steps; replay button.

### Step 7 — Switch over
- FastAPI serves `web/dist` at `/`; keep the old page at `/legacy` for one round of comparison.
- Build step: `pnpm --dir web build` (run on the VM before restart; Node only at build time).
- Remove `/legacy` and `scripts/seed_viewer/index.html` once the user signs off.

### Step 8 — Quality
- Playwright tests ported from the earlier checks (filters, URL state, profile, ←/→, shortlist,
  export, tour, phone width, dark mode, cookie-less access-key).
- GitHub Actions: Biome, typecheck, Vitest, build on every push.
- Update `docs/` with a short "run & deploy" section.

Each step is committed separately and pushed to `jubayer-juhan-dev/talent-seed`; the live link
stays up between steps.

## Verification (each step)
- API: curl old vs new endpoints, JSON diff identical (step 1); `/api/docs` loads.
- UI: Playwright on desktop (1400px) and phone (390px), light and dark, no console errors, no
  horizontal scroll; screenshots compared with the current page.
- Access: no key → 401; `?key=` works with cookies blocked; CSV carries unverified/draft/attribution.
- Live: after switch-over, test through the Cloudflare link with the real key.

## Open items
- Client sign-off on adding a Node *build* step (handoff said "not needed", not forbidden).
- Rotate the broad GitHub token before more pushes / the P3 login lookup.
