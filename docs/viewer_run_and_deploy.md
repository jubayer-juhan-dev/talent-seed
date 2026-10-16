# Talent Seed viewer: run, change, deploy

## What runs where

```
Browser ── Cloudflare quick tunnel ── FastAPI (uvicorn, 127.0.0.1:8765) ── data/talent_seed.duckdb (read-only)
           talent-seed-tunnel           talent-seed-viewer                  data/github_logins.sqlite
                                         ├─ /api/*   JSON API                data/enrichment.sqlite
                                         └─ /        React app (web/dist)
```

| Piece | Where | Notes |
|---|---|---|
| API | `viewer_api/` (FastAPI) | Read-only DuckDB, one connection per request. Docs at `/api/docs`. |
| Web app | `web/` (React 19, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query/Router) | Built to `web/dist`, served by the API. |
| Services | `deploy/*.service` → `/etc/systemd/system/` | Restart on failure and at boot. |
| Access key | `/etc/talent-seed-viewer.env` (`TALENT_SEED_KEY=…`, root-only) | Not in git. Needed as `?key=` on the link, `X-Access-Key`, or cookie. |
| Public link | `scripts/viewer_link.sh` prints it | The trycloudflare.com address changes when the tunnel restarts. |

## Everyday commands (on the VM)

```bash
scripts/viewer_link.sh                            # current link with the key
systemctl status talent-seed-viewer talent-seed-tunnel
systemctl restart talent-seed-viewer              # after API (Python) changes
tail -f scratch/seed_viewer.log                   # API log
```

## Change the web app

```bash
cd web
TALENT_SEED_KEY=$(cut -d= -f2- /etc/talent-seed-viewer.env) pnpm dev   # http://127.0.0.1:5173, proxies /api
pnpm check && pnpm test                            # lint + types, unit tests
pnpm build                                         # writes web/dist; the live site serves it right away
```

No restart is needed after `pnpm build`: the API reads `web/dist` on each request.

## Change the API

1. Edit `viewer_api/` (SQL is in `queries.py`, response shapes in `models.py`).
2. `systemctl restart talent-seed-viewer`
3. If response shapes or parameters changed: `cd web && pnpm gen:api` (regenerates `src/api/schema.d.ts`;
   CI fails if `web/openapi.json` is stale).

## Use the data from Claude (MCP)

`viewer_api/mcp_server.py` exposes the same queries to Claude as MCP tools: `meta`, `overview`,
`search_ecosystems`, `search_people`, `get_person`, `export_csv` (writes to `exports/`) and `set_ai_enriched`.
It opens the DuckDB file read-only and in-process, so it needs neither the viewer running nor the access key.

- Claude Code: `.mcp.json` registers it. Start `claude` anywhere in the repo and approve the `talent-seed` server.
- Claude Desktop / other clients: run `uv run python -m viewer_api.mcp_server` (stdio) from the repo root.

During a database rebuild the tools return "database is being rebuilt". After changing `queries.py`, restart the
session (or `/mcp` → reconnect) so the server reloads.

## Tests

| Kind | Command | Where it runs |
|---|---|---|
| Lint + types | `pnpm check` (web/) | CI and locally |
| Unit (Vitest) | `pnpm test` (web/) | CI and locally |
| Browser (Playwright, desktop + phone) | `TALENT_SEED_KEY=$(cut -d= -f2- /etc/talent-seed-viewer.env) pnpm e2e` (web/) | On the VM only: they need the real database. Run before deploying UI changes. |

CI (`.github/workflows/ci.yml`) runs on every push: web lint/types/unit tests/build, Python compile, and the
OpenAPI-types check.

## Data jobs

```bash
uv run scripts/m4_build_talent_seed.py                       # rebuild talent_seed.duckdb (~5 min; viewer shows 503 meanwhile)
uv run scripts/m5_lookup_github_logins.py --cohort P3 --wait # GitHub logins (token in /root/.github_token)
uv run scripts/set_ai_enriched.py --by "<model>" gh:123 …    # mark people AI-enriched (--unset, --list, --file)
```

Long jobs: run them with `systemd-run --unit=<name> …` so they survive a closed session.

## Roll back to the first viewer

The first viewer (`scripts/seed_viewer/`) was removed after sign-off. It is in git history: `git show a11fccc:scripts/seed_viewer/index.html`.
