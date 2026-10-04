# talent_seed record — DRAFT 0.1 (option B)

**Status: draft by assumption.** No client spec (`spec_v0_2.md`) exists. The field list comes from
the Milestone 3 brief, and the design principles come from the ProspectMind architecture diagram
(`docs/prospectmind_architecture.png`): evidence and provenance, confidence, refresh/staleness and
shared IDs. Rename or reshape fields once the client's schema is available. Every threshold behind
these fields is in `config/talent_seed_thresholds.toml`, tagged `EC` or `ASSUMPTION`.

Output of `scripts/inspect_developer.py`: one JSON file per input. It contains `{input,
match_count, note, records[]}`, plus `candidates[]` when an input matches more than 25 developers.

## Record fields

| field | meaning |
|---|---|
| `canonical_developer_id` | ODD's developer key (shared ID) |
| `match_methods` | how the input matched: `COMMIT_AUTHOR_EMAIL`, `COMMIT_AUTHOR_NOREPLY_EMAIL` or `ODD_GITHUB_ID` |
| `display_name` | the author name with the most commits |
| `github` | `login`, `user_id`, `node_id`, `resolution_method` (NOREPLY / ODD_GITHUB_ID / COMMIT_API / UNRESOLVED), `resolution_commit_sha`, `resolution_repo`, `confidence` (HIGH / MEDIUM / LOW / NONE), `corroborated_by_odd_github_id`, `evidence[]`, `conflicts[]` |
| `contact_points[]` | one entry per author email. `email_status` is always `UNVERIFIED`. Also `is_github_noreply`, `is_placeholder`, `shared_by_n_developers`, first/last seen and `source_table`. No employer is inferred from the email domain. |
| `name_variants[]` | author names with first/last seen and commit counts |
| `location` | ODD geocoded location, if any, with `source_table` and `geocoded_at` |
| `first_commit_date`, `last_activity_date` | dates |
| `repository_count`, `ecosystem_count` (top-level chains), `sub_ecosystem_count`, `commit_count` | counts |
| `*_excluding_inherited` | the same counts without fork/import history |
| `tenure_segment`, `tenure_days` | ESTABLISHED / EMERGING / NEWCOMER / UNKNOWN |
| `activity_segment`, `active_days_in_window`, `max_active_days_in_28d`, `activity_segment_reason` | FULL_TIME / PART_TIME / ONE_TIME / UNKNOWN over the last 84 days |
| `exclusivity` | `status` (EXCLUSIVE / MULTICHAIN / UNKNOWN) from ODD `is_exclusive`, plus the fallback measure (distinct top-level ecosystems in the window) |
| `odd_contribution_rank_latest`, `odd_tenure_latest` | EC's own per-ecosystem labels, for comparison |
| `priority_cohort`, `priority_cohort_detail` | P1 / P2 / P3 / HOLD, with the rule number, reason and `status = DRAFT_ASSUMPTION` |
| `data_quality_flags[]` | PROBABLE_BOT, MERGED_IDENTITY, PLACEHOLDER_EMAIL, INHERITED_HISTORY, REPO_MANY_ECOSYSTEMS, GITHUB_CONFLICT, … |
| `repos[]` | per repo: commits, active days, first/last active, top-level and sub-ecosystems, dropped category tags, inherited-history flag |
| `ecosystems[]` | relation list: level (TOP_LEVEL / SUB_ECOSYSTEM), repo_ids, commits, last_active_date |
| `lineage` | `source_snapshot_id`, `source_snapshot_date`, `as_of_activity_date`, `activity_window`, `source_tables`, GitHub API usage, `thresholds_config`, `generated_at`, CC BY 4.0 attribution |
