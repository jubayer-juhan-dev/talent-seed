# Handoff: design the Talent Seed web viewer

You're picking up the web viewer for ProspectMind Talent's "Talent Seed" data. The data pipeline is
finished; your job is the **webpage**: its design, UX and the small API behind it. Work in
`/root/talent-seed` on this Linux VM. Python is managed with `uv` (binary at `~/.local/bin/uv`).

## What the data is

Electric Capital's Open Dev Data (ODD) is a public dataset of crypto/Web3 open-source developers,
licensed **CC BY 4.0**. Attribution to Electric Capital must stay visible on the page. From it we
built one row per **person** (a developer, with linked duplicate IDs merged), carrying:
- activity and tenure segments;
- a priority cohort **P1 / P2 / P3 / HOLD**: who a recruiter should look at first;
- their repos, ecosystems (Ethereum, Solana, …) and commit emails.

Numbers for snapshot `20261002T130207` (activity data through 2026-09-24):
- 3,499,818 people.
- P1 6,759 · P2 17,560 · P3 27,956 · HOLD 3,447,543. Most HOLD people simply weren't active in the
  last 84 days.

The users are **recruiters / talent sourcers**, not engineers. The page should answer: *who are the
best active crypto developers for a given chain or skill area, and why is each one ranked where they
are?*

## Where things are

| Path | What |
|---|---|
| `data/talent_seed.duckdb` | **The database the viewer reads.** DuckDB file, 1.1 GB. |
| `scripts/seed_viewer/server.py` | Current backend: Python stdlib `http.server` + `duckdb`, JSON API |
| `scripts/seed_viewer/index.html` | Current frontend: one HTML file, vanilla JS, no build step |
| `docs/talent_seed_tables.md` | Table and column reference, plus the rules behind the cohorts. **Read this first.** |
| `config/talent_seed_thresholds.toml` | Every threshold and cohort rule, each tagged EC (Electric Capital method) or ASSUMPTION |
| `docs/data_dictionary.md` | The raw ODD tables (you shouldn't need these) |
| `docs/prospectmind_architecture.png` | The client's product architecture diagram, for context and naming |
| `scripts/m4_build_talent_seed.py` | Builds the database (~5 min). **Don't change it** for UI work. |

## Tables in `data/talent_seed.duckdb`

- **`talent_seed`**, one row per person, key `person_id`. `person_id` is `gh:<github_user_id>` or
  `odd:<id>`. Columns:
  - person_id, primary_canonical_developer_id, canonical_developer_ids, n_canonical_ids,
    display_name, n_names
  - github_user_id, github_login, github_login_source, github_resolution_method,
    github_corroborated_by_odd_id, github_candidate_commit_sha, github_candidate_repo,
    github_confidence (HIGH / MEDIUM / LOW / NONE)
  - location, country
  - first_commit_date, first_crypto_commit_date, last_crypto_activity_date, last_activity_date
  - repository_count, repository_count_excluding_inherited, ecosystem_count,
    ecosystem_count_excluding_inherited, sub_ecosystem_count, top_level_ecosystems (list)
  - commit_count, commit_count_bot, commit_count_ai_agent, commit_count_excluding_inherited
  - tenure_days, active_days_in_window, max_active_days_in_28d
  - exclusivity_eco_days, exclusivity_exclusive_days, top_level_ecosystems_in_window (list)
  - odd_contribution_rank_asof
  - flag_probable_bot, flag_github_conflict, flag_linked_ids, flag_activity_table_gap,
    flag_bad_commit_dates
  - tenure_segment (ESTABLISHED / EMERGING / NEWCOMER / UNKNOWN), activity_segment (FULL_TIME /
    PART_TIME / ONE_TIME / UNKNOWN), exclusivity (EXCLUSIVE / MULTICHAIN / UNKNOWN),
    exclusivity_method, distinct_top_level_ecosystems_in_window
  - priority_cohort, priority_cohort_rule, priority_cohort_reason,
    priority_cohort_status (= DRAFT_ASSUMPTION)
  - as_of_activity_date, activity_window_start, source_snapshot_id, source_snapshot_date,
    source_tables
- **`talent_seed_contact_points`**, person × email: value, email_status (always UNVERIFIED),
  is_github_noreply, is_placeholder, shared_by_n_developers, author_names, first/last_seen_at,
  n_commits.
- **`talent_seed_repos`**, person × repo: repo_name, repo_url, commits, active_days,
  first/last_active_date, inherited_history (fork/copied history), is_crypto_repo,
  first/last_original_date, num_stars.
- **`talent_seed_ecosystems`**, person × ecosystem: level (TOP_LEVEL = a chain like Ethereum;
  SUB_ECOSYSTEM = a project like Uniswap), ecosystem_name, repo_count, commits, last_active_date.
- **`talent_seed_members`**, person ↔ ODD developer ids: link_method SINGLE_ID / SAME_GITHUB_USER_ID.
- **`talent_seed_runs`**: build metadata (snapshot, as-of date, row counts, attribution).

## Current API (`server.py`)

| Endpoint | Returns |
|---|---|
| `GET /api/meta` | `{run, cohorts:[{k,n}], chains:[{k,n}], countries:[{k,n}]}` |
| `GET /api/people?cohort=&activity=&tenure=&exclusivity=&country=&chain=&q=&hide_flagged=1&sort=&dir=&page=` | `{total, page, page_size:50, rows:[…]}` |
| `GET /api/person?id=gh:1076145` | `{person, members, contacts, ecosystems, repos (100 most recent), repo_total}` |

- Sort keys: commits, last_activity, first_commit, repos, ecosystems, active_days, name.
- `q` matches a name/login substring, an exact email, or a `gh:…` / `odd:…` id.
- Queries take 0.2–1.5 s over 3.5M rows.
- You may extend the API (new endpoints, aggregates, facets, CSV export…). Keep it parameterized and
  read-only.

## How to run and test

The viewer is usually already running on port 8765. Check with `ps aux | grep seed_viewer`.

To restart it:
```
pkill -f seed_viewer/server.py
cd /root/talent-seed && nohup ~/.local/bin/uv run scripts/seed_viewer/server.py --port 8765 > scratch/seed_viewer.log 2>&1 &
```
The server reads `index.html` on every request, so frontend edits need only a browser refresh.
Restart only after editing `server.py`.

Test the API with curl, e.g. `curl -s "localhost:8765/api/people?cohort=P1&hide_flagged=1" | head -c 500`.

The user views it from their own computer via `ssh -L 8765:localhost:8765 root@212.47.72.157`,
then http://localhost:8765.

## Hard rules

1. **Read-only.** Open DuckDB with `read_only=True`, one connection per request, closed afterwards
   (as `server.py` does now). A rebuild (`m4_build_talent_seed.py`) needs the write lock. Never
   write to the database from the viewer, and never touch `raw_open_dev_data/` or `data/odd.duckdb`.
2. **No new services.** The client brief forbids adding Postgres, a graph database, or a service
   architecture in this phase. Stay with Python + DuckDB + a static page. A frontend library loaded
   from a CDN is fine; a Node build pipeline is not needed.
3. **Bind to 127.0.0.1 only.** The page shows real people's emails and has no login. Don't expose
   it on a public port.
4. **Honesty in the UI:**
   - Label emails "unverified".
   - Show that cohorts are a **draft** (`priority_cohort_status = DRAFT_ASSUMPTION`) until the
     client confirms them.
   - Show the snapshot date / "activity through" date.
   - Never infer or show an employer from an email domain.
5. **Attribution:** keep the "Data from Electric Capital Open Dev Data, CC BY 4.0" credit visible.

## Data caveats the design should surface (not hide)

- **"Why this cohort":** every person has `priority_cohort_reason` and `priority_cohort_rule`. Make
  the reasoning visible; it's the main trust signal for a recruiter.
- **GitHub match quality:** many people have a GitHub id but **no login**. A login needs an API
  lookup, which isn't done yet. Show `github_confidence` and link to `https://github.com/<login>`
  only when the login is known.
- **Commit counts mislead:**
  - Forks and copied history inflate `commit_count`. Prefer `active_days_in_window`,
    `*_excluding_inherited`, and repos where `is_crypto_repo AND NOT inherited_history`.
  - The default sort is active days (last 84 days), on purpose.
- **Remaining bad actors:** a few automation accounts still sit in P1, e.g. "Tangem" (962k commits)
  and "Lambda - Automatic Price Updator". The flags `flag_probable_bot` / `flag_github_conflict`
  exist, and the "hide bots & conflicts" filter defaults to on.
- **Exclusivity is UNKNOWN for most active people** (no chain-mapped work in the window). Treat
  UNKNOWN as "not applicable", not as missing data.
- **One person can still appear more than once** when their IDs share no GitHub account (see
  Samuel Stroschein in `docs/talent_seed_tables.md`).

## Design brief (open; propose before big changes)

The current page works but is a plain data table. The user wants it redesigned so the seed data is
**easy to explore**. Ideas to weigh, not requirements:

- **An overview first:**
  - cohort counts
  - active developers per chain (Ethereum, Solana, …)
  - tenure/activity mix
  - top countries
  - a small chart or two (DuckDB can aggregate quickly; add an endpoint)
- **Fast shortlisting:**
  - chain and sub-ecosystem filters (e.g. "Uniswap", "Anza"), cohort, activity, tenure, country
  - keyword search
  - saved views via URL query params
- **A person profile recruiters can read in ten seconds:** who they are, where, which chains, how
  active lately (an activity sparkline over the 84 days would need a new endpoint over
  `talent_seed_repos` or the raw data; check feasibility), why this cohort, contact points with
  caveats, top original crypto repos.
- **Shortlist export** (CSV of the current filter) for outreach tools, with caveats preserved.

Start by reading `docs/talent_seed_tables.md` and the two viewer files. Then run the viewer, look at
the current page, and propose a short design plan to the user before rewriting.
