# talent_seed tables (Milestone 4)

Built by `scripts/m4_build_talent_seed.py` (~5 min) from `data/odd.duckdb` into
`data/talent_seed.duckdb` (1.1 GB). Parquet copies are in `exports/<snapshot_id>/` (718 MB). Rules
and thresholds are in `config/talent_seed_thresholds.toml`. Every row carries
`source_snapshot_id`, `source_snapshot_date` and `source_tables`.

Snapshot `20261002T130207`; activity is as of 2026-09-24; the 84-day window starts 2026-07-03.

| table | rows | one row = |
|---|---|---|
| `talent_seed` | 3,499,818 | one person (key `person_id`) |
| `talent_seed_members` | 3,513,049 | one ODD canonical developer id → its person, with `link_method` |
| `talent_seed_contact_points` | 4,338,192 | person × author email; always `email_status = 'UNVERIFIED'` |
| `talent_seed_repos` | 8,502,425 | person × repo (commits, active days, first/last active, inherited history) |
| `talent_seed_ecosystems` | 1,652,787 | person × ecosystem (`TOP_LEVEL` chain or `SUB_ECOSYSTEM`); crypto ecosystems only |
| `talent_seed_runs` | 1 per build | build time, config used, row counts, attribution |

## person_id and identity linking

- `gh:<github_user_id>`: one or more canonical ids that resolve to the same GitHub account, through
  ODD's decoded node id or the numeric id in a noreply email. 12,564 people link 2–11 ids.
- `odd:<canonical_developer_id>`: an id that was not linked. This covers ids with no GitHub id,
  ids with several GitHub ids (a conflict), bots and AI agents.
- **Known limit:** ids with no GitHub id at all can't be linked. Samuel Stroschein stays split:
  `gh:35429197` plus `odd:3595743` and `odd:3596948`. All three are HOLD, because his recent work is in repos that aren't crypto-tagged.

## Key talent_seed columns

`display_name`, `github_user_id`, `github_login` (+ `github_login_source`),
`github_resolution_method` (NOREPLY / ODD_GITHUB_ID / UNRESOLVED), `github_confidence`,
`github_candidate_commit_sha`/`repo` (for a later commit-API lookup), `location`, `country`,
`first_commit_date`, `last_activity_date`, `first_crypto_commit_date` (tenure is measured from this), `last_crypto_activity_date`, `repository_count`, `ecosystem_count`,
`sub_ecosystem_count`, `commit_count` (+ `*_excluding_inherited`), `tenure_segment`, `tenure_days`,
`activity_segment`, `active_days_in_window`, `max_active_days_in_28d`, `exclusivity`
(+ `exclusivity_method`), `top_level_ecosystems`, `odd_contribution_rank_asof`, the `flag_*`
columns, `priority_cohort` (+ `_rule`, `_reason`, `_status = DRAFT_ASSUMPTION`).

GitHub resolution here is offline only. The commit API isn't called in bulk.

## Snapshot 20261002T130207 results

| cohort | people |
|---|---|
| P1 | 6,759 |
| P2 | 17,560 |
| P3 | 27,956 |
| HOLD | 3,447,543 (3,393,440 have no original crypto commits in the last 84 days; 50,717 are bots) |

Two rules were added on 2026-10-04 (see config):
- **Bot names:** names and logins such as "Gerrit User", "...-bot", "Merge Robot" and "Weblate" are
  treated as bots.
- **Original crypto work only:** activity, tenure and cohort count only commits in crypto-tagged
  repos that were authored after the repo was created. Before these two rules, P1–P3 held ~237k
  people, inflated by work on Linux, LLVM and other non-crypto repos.

## Checks

- Σ `commit_count` = 491,574,165, which equals ODD's commits row count.
- `person_id` is unique.
- No non-crypto ecosystems remain.
- The Milestone 3 test developers matched their `inspect_developer.py` records before the 2026-10-04
  rules. `inspect_developer.py` doesn't apply those two rules yet.
