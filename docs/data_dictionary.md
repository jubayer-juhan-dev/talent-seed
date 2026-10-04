# Open Dev Data (ODD) — Data Dictionary

Source: Electric Capital Open Dev Data, https://github.com/electric-capital/open-dev-data
License: CC BY 4.0 — attribution to Electric Capital required on any derived product.
Snapshot inspected: `20261002T130207` (manifest `created` 2026-10-02T13:37:08Z).
Manifest: https://data.opendevdata.org/manifest.json — 19 Parquet files, 51.2 GB total.

**How this was built:** I introspected every schema with `DESCRIBE` and took row counts from
Parquet footers (`parquet_file_metadata`). Value domains come from Parquet column
statistics across all row groups. Sample distributions come from the first 2–3M rows of a
file, so they are indicative, not population-wide. Statements marked *(inferred)* are my
reading of the data, not EC documentation. The quoted descriptions come from the manifest.

The `tui --lite` set is only `eco_mads`, `ecosystems`, `ecosystems_repos` and `repos`. It
contains **no commit or developer tables**. The other tables were inspected remotely over HTTP
(footer and first row group only). `canonical_developers` and
`canonical_developer_locations` were downloaded in full (121 MB).

---

## Entity overview

```
                      ecosystems_child_ecosystems(_recursive)
                               parent_id / child_id
                                       │
organizations ──< ecosystems_organizations >── ecosystems ──< ecosystems_repos(_recursive) >── repos
      ▲                                           │                                         │  ▲
      └──────────────── repos.organization_id ────┼─────────────────────────────────────────┘  │
                                                  │                                            │
          eco_mads (ecosystem_id, day)            │                                            │
          eco_developer_activities ───────────────┤ ecosystem_id                     repo_id ──┤
          eco_developer_28d_activities ───────────┤                                            │
          eco_developer_contribution_ranks ───────┤                                            │
          eco_developer_tenures ──────────────────┤                                            │
          repo_developer_activities ──────────────┘ (ecosystem_id + repo_id)                   │
          repo_developer_28d_activities, developer_activities, commits ────────────────────────┘
                     │ canonical_developer_id
                     ▼
            canonical_developers.id ──1:0..1── canonical_developer_locations.canonical_developer_id
```

Join keys used everywhere:

| Key | Points to |
|---|---|
| `canonical_developer_id` | `canonical_developers.id` |
| `repo_id` | `repos.id` |
| `ecosystem_id`, `parent_id`, `child_id` | `ecosystems.id` |
| `organization_id` | `organizations.id` |

---

## Identity tables

### canonical_developers — 3,513,047 rows
"Canonical developer identity mappings." **One row = one canonical (de-duplicated) developer.**

| column | type | notes |
|---|---|---|
| `id` | INTEGER | **PK**, unique (3,513,047 distinct). The canonical developer ID used by every activity table. |
| `primary_developer_email_identity_id` | INTEGER | Never null. Points to an email-identity table that is **not published** in ODD, so it can't be joined. |
| `primary_github_user_id` | VARCHAR | GitHub **GraphQL node ID**, not a login. 2,280,027 non-null (65%), all distinct. Formats: `U_kg…` new user IDs (1.72M), `MDQ6…` legacy user IDs (563k), `BOT_…`/`MDM6…` bot accounts (~1.7k). |

Both node-ID formats decode offline to the numeric GitHub user ID:
- `MDQ6VXNlcjE5NTA3NDgy` → base64 → `04:User19507482`
- `U_kgDOClp4rg` → base64url `kgDOClp4rg` → msgpack `[0, 173701294]`
- `MDM6Qm90NjI0MjM4NzY=` → `03:Bot62423876`

### canonical_developer_locations — 923,905 rows
"Canonicalized developer geographic/location data." **One row = one developer's geocoded
location.** `canonical_developer_id` is unique, so the relationship is 1:0..1. 26% of canonical
developers have a row.

| column | type | notes |
|---|---|---|
| `canonical_developer_id` | INTEGER | PK/FK → `canonical_developers.id` |
| `created_at` | TIMESTAMPTZ | when geocoded (samples: 2025-06 to 2025-07) |
| `input` | VARCHAR | free-text location as the developer wrote it, e.g. "San jose" or "USA, 3rd rock from sun, Milky Way…" *(inferred: GitHub profile location)* |
| `country`, `admin_level_1`, `admin_level_2`, `locality`, `sublocality`, `formatted_address` | VARCHAR | geocoder output; `country` non-null for 878,827 rows |
| `lat`, `lng` | DOUBLE | |
| `raw` | VARCHAR | raw geocoder JSON (Google Places) |

---

## Commit-level fact

### commits — 491,574,165 rows (22.0 GB)
"Individual commit records with developer mappings." **One row = one commit in one repo.**

| column | type | notes |
|---|---|---|
| `id` | BIGINT | PK |
| `repo_id` | INTEGER | FK → `repos.id` |
| `sha1` | VARCHAR | full 40-char commit SHA |
| `created_at` | TIMESTAMPTZ | ingestion time *(inferred)* |
| `additions`, `deletions` | INTEGER | |
| `authored_at`, `authored_at_offset` | TIMESTAMPTZ, INTEGER | author timestamp and TZ offset. Stats show outliers from 1970-01-01 to 2206-07-27. |
| `committed_at`, `committed_at_offset` | TIMESTAMPTZ, INTEGER | |
| `commit_author_name` | VARCHAR | raw git author name |
| `commit_author_email` | VARCHAR | raw git author email. The only place emails appear in ODD. No committer name/email. |
| `canonical_developer_id` | INTEGER | FK → `canonical_developers.id` |
| `is_bot` | UTINYINT | 0/1 |

Sample of the first 2M rows: every row had email, name and `canonical_developer_id`. 18.8% used
`@users.noreply.github.com` emails and 9.8% were `is_bot=1` (e.g. `bors@rust-lang.org`). There were
56k developers and 64k distinct emails. One developer had 8 email variants and 3 names, which shows
the canonicalisation merges identities. (sha1, repo_id) was unique in the sample.

**Physical layout:** row groups aren't clustered by developer or repo (each row group covers
almost the full ID range). A lookup by developer or email has to scan all 22 GB unless we build a
sorted or indexed copy.

---

## Developer activity aggregates (built from commits)

### developer_activities — 101,190,240 rows
"Core daily developer–repo activity aggregates built from commits."
**One row = (repo_id, day, canonical_developer_id)** with `num_commits` > 0. No ecosystem column.

### repo_developer_activities — 923,255,094 rows
"Repository-level daily developer activity records." **One row = (ecosystem_id, repo_id, day,
canonical_developer_id).** This is `developer_activities` fanned out to every ecosystem the
repo belongs to, recursively, so one commit-day appears once per ecosystem.

| column | notes |
|---|---|
| `ecosystem_id`, `repo_id`, `day`, `canonical_developer_id`, `num_commits` | |
| `is_explicit` | repo is directly tagged to this ecosystem (vs. inherited through a child) *(inferred, same name as in `ecosystems_repos_recursive`)* |
| `is_chain` | 0/1, whether `ecosystem_id` is a chain |
| `is_direct_exclusive`, `is_indirect_exclusive`, `exclusive_at_connection` | BOOLEAN. **Properties of the repo↔ecosystem link**, copied from `ecosystems_repos_recursive`. They are not developer exclusivity. |
| `exclusive_till` | DATE, null in 99.6% of rows (919.7M of 923.3M); range 2008-01-02 to 2025-09-24 |

### repo_developer_28d_activities — 757,269,696 rows
"Repository-level 28-day rolling activity windows." **One row = (repo_id, canonical_developer_id,
day)** where `day` is a window end. `l28_days` (1–28) appears to count active days in the trailing
28 days *(inferred)*. `original_day` is the underlying activity day. The manifest says "with
ecosystem associations", but the file has **no** ecosystem column.

### eco_developer_activities — 785,006,497 rows
"Daily developer activities at the ecosystem level with exclusivity flags."
**One row = (ecosystem_id, day, canonical_developer_id)** with `repo_ids INTEGER[]`, `num_commits`
and **`is_exclusive BOOLEAN`**. This is the developer-exclusivity flag. In the first 2M rows it was
61% true and 39% false.

### eco_developer_28d_activities — 4,074,260,639 rows (12.7 GB)
"28-day rolling ecosystem activity windows used to compute all_devs, exclusive_devs, and
multichain_devs." **One row = (ecosystem_id, canonical_developer_id, day)**, with `repo_ids[]`,
`num_commits`, `original_day`, **`is_exclusive_28d BOOLEAN`** and `l28_days` (1–28).

### eco_developer_contribution_ranks — 4,074,260,639 rows
"Developer contribution classifications over 84-day windows: full_time, part_time, one_time."
**One row = (ecosystem_id, canonical_developer_id, day)**.

| column | notes |
|---|---|
| `points` | 1–10 |
| `points_28d`, `points_56d` | 0–10 |
| `contribution_rank` | `full_time` / `part_time` / `one_time`. In the first 3M rows, `one_time` always had `points=1`. `full_time` and `part_time` both span points 1–10, so the rule isn't a simple threshold on `points`. EC's exact formula must be confirmed in Milestone 3. |

### eco_developer_tenures — 4,036,560,651 rows
"Developer tenure segments by first blockchain commit: devs_0_1y, devs_1_2y, devs_2y_plus."
**One row = (ecosystem_id, canonical_developer_id, day)** with `tenure_days` and `category`
(UTINYINT). From the first 3M rows:

| category | tenure_days | maps to eco_mads |
|---|---|---|
| 0 | 0–365 | `devs_0_1y` |
| 1 | 366–730 | `devs_1_2y` |
| 2 | ≥ 731 | `devs_2y_plus` |
| 9 | negative (−1992 to −1) | data anomaly: active before first commit? Footer stats show category max = 9 and tenure_days min = −1. |

### eco_mads — 10,596,544 rows (in lite)
"Monthly Active Developer metrics per ecosystem/day." **One row = (ecosystem_id, day)**,
covering 2015-01-01 to 2026-09-24 and 8,476 ecosystems. Aggregate counts only: `all_devs`,
`exclusive_devs`, `multichain_devs`, `num_commits`, `devs_0_1y`, `devs_1_2y`, `devs_2y_plus`,
`one_time_devs`, `part_time_devs`, `full_time_devs`. In the samples, `exclusive_devs +
multichain_devs = all_devs`. For example, Ethereum on 2026-09-24 had 14,307 all_devs = 3,264
exclusive + 11,043 multichain.

---

## Taxonomy

### ecosystems — 13,328 rows (in lite)
**One row = one ecosystem node** in EC's crypto-ecosystems taxonomy. `id` is the PK.
Columns: `name`, `launch_date`, `derived_launch_date`, `earliest_first_party_commit_date`,
`earliest_first_party_repo_id`, `earliest_repo_commit_date`, `earliest_repo_id`, and the
flags `is_crypto`, `is_category`, `is_virtual`, `is_chain`, `is_multichain` (0/1).
Examples: Bitcoin = 1, Ethereum = 2, Solana = 391 (all `is_chain=1`), Uniswap = 4074.
280 ecosystems have `is_chain=1`.
**Caveat:** this table mixes real ecosystems with categories and internal cohort lists, e.g.
"Top 200 2021Q3", "cohort_snapshot_20250629_200819" and "__dup__All Web3 Ecosystems…". Ethereum
has about 40 such parents. "Top-level ecosystem" can't be defined as "has no parent". Milestone 3
needs an explicit rule, such as rolling up to the nearest `is_chain=1` ancestor and ignoring
`is_category` parents.

### ecosystems_child_ecosystems — 29,976 rows
Direct hierarchy edges. **One row = (parent_id → child_id)**, plus `created_at` and `connected_at`.

### ecosystems_child_ecosystems_recursive — 1,829,080 rows
Transitive closure. **One row = one path from parent_id to child_id.** The same pair can repeat
with different paths. Columns: `ecosystem_ecosystem_paths INTEGER[]`,
`ecosystem_chain_ecosystem_paths INTEGER[]` (the chain ecosystems along the path),
`connection_dates DATE[]` and `connected_at`.

### ecosystems_repos — 3,082,088 rows (in lite)
Direct tagging. **One row = (ecosystem_id, repo_id)**, unique, plus `id`, `created_at` and
`connected_at`. Some repos are tagged to many ecosystems. The largest is
`curtis0x/ecosystems-v2` with 242; several DeFi repos have 35–41.

### ecosystems_repos_recursive — 29,373,691 rows
Repo membership including inheritance from child ecosystems. **One row = (ecosystem_id, repo_id,
path)**. Columns: `path INTEGER[]`, `distance`, `is_explicit`, `is_direct_exclusive`,
`is_indirect_exclusive`, `exclusive_at_connection`, `exclusive_till`, `connected_at`.

### repos — 2,648,396 rows (in lite)
**One row = one GitHub repository.** `id` is the PK. `name` is `owner/repo`. `link` is
`https://github.com/owner/repo`. Also `github_graphql_id`, `organization_id` (FK, nullable),
`num_stars`, `num_forks`, `num_issues`, `repo_created_at` and `is_blacklist` (0/1).

### organizations — 95,150 rows
**One row = one GitHub org.** Columns: `id`, `name`, `link`, `created_at`, `github_created_at`.

### ecosystems_organizations — 7,187 rows
**One row = (ecosystem_id, organization_id)**, with `is_first_party` (0/1).

---

## Lineage convention for derived data

Every derived row will carry `source_snapshot_date` (from the snapshot ID, e.g. `2026-10-02`)
plus `source_snapshot_id` (`20261002T130207`) and `source_tables` (the list of ODD tables
read). Raw Parquet files are read-only (`chmod 444`) and never rewritten.

---

## Derived tables in data/odd.duckdb (not part of ODD)

`data/odd.duckdb` holds one **view** per raw Parquet file, plus:

### _odd_lineage — 20 rows
**One row per table:** `table_name`, `source_snapshot_id`, `source_snapshot_date`,
`source_file`, `source_url`, `size_bytes`, `b3sum`, `row_count`.

### dev_identity_variants — 5,148,762 rows (built by scripts/m2_build_db.py)
**One row = (canonical_developer_id, commit_author_email, commit_author_name).** Built from one
full scan of `commits`. The counts reconcile exactly: Σ n_commits = 491,574,165.

| column | notes |
|---|---|
| `email_norm` | `lower(trim(commit_author_email))`. The table is sorted on it for lookups. |
| `first_seen_at`, `last_seen_at` | min/max `authored_at`, **excluding** dates before 2005-04-01 or after the snapshot date |
| `n_commits`, `n_commits_bad_date`, `n_bot_commits`, `n_repos` | |
| `latest_sha1`, `latest_sha1_repo_id` | most recent commit for this variant, used for the GitHub commit API lookup |
| `source_snapshot_id`, `source_snapshot_date`, `source_tables` | lineage |

Data-quality facts measured on the full snapshot:
- 8,546,977 commits (1.7%) have an author date before 2005-04-01 or after the snapshot date.
- 58,028,249 commits (11.8%) have `is_bot=1`.
- 1,678,765 commits have an empty author email.
- 106,409 emails map to more than one canonical developer. Most are placeholders such as
  `none@none` (2,706 devs), `unknown`, `you@example.com` and `devnull@localhost`, so an email
  lookup must not assume a single match.
- Canonical developer 5195 is `github-actions[bot]`, with 246 different author names merged
  into it.
- 2 `canonical_developer_id` values in `commits` (3558658 and 3606561, 90 commits in all) are
  missing from `canonical_developers`.
