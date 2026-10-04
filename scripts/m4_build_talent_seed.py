"""Milestone 4: build the full-population talent_seed tables.

Reads data/odd.duckdb (read-only; raw Parquet untouched) and writes data/talent_seed.duckdb plus
Parquet exports in exports/<snapshot_id>/. Same rules and thresholds as scripts/inspect_developer.py
(config/talent_seed_thresholds.toml), applied set-based to every developer, with identity linking:
one talent_seed row = one PERSON (canonical developer ids sharing one GitHub account).

Tables (every row carries source_snapshot_id, source_snapshot_date, source_tables):
  talent_seed                 one row per person
  talent_seed_members         person <-> canonical_developer_id, with link method
  talent_seed_contact_points  person x author email (email_status = 'UNVERIFIED')
  talent_seed_repos           person x repo
  talent_seed_ecosystems      person x ecosystem (TOP_LEVEL chain / SUB_ECOSYSTEM)
  talent_seed_runs            one row per build run

Bulk GitHub resolution is offline only (NOREPLY / ODD_GITHUB_ID). The commit API is not called in
bulk (needs a token and many hours); unresolved persons carry a candidate commit SHA for later.

Usage: uv run scripts/m4_build_talent_seed.py
"""

import json
import time
import tomllib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
ODD_DB = ROOT / "data" / "odd.duckdb"
OUT_DB = ROOT / "data" / "talent_seed.duckdb"
CONFIG = ROOT / "config" / "talent_seed_thresholds.toml"
FLAG_COLUMNS = {"PROBABLE_BOT": "flag_probable_bot", "GITHUB_CONFLICT": "flag_github_conflict"}


def sql_list(values) -> str:
    return ", ".join("'" + str(v).replace("'", "''") + "'" for v in values)


def cohort_case(cfg: dict) -> str:
    """Translate the [priority_cohort] rules into SQL CASE expressions (first match wins)."""
    pc = cfg["priority_cohort"]
    whens = []
    for i, rule in enumerate(pc["rules"], 1):
        conds = []
        if "activity_segment" in rule:
            conds.append(f"activity_segment IN ({sql_list(rule['activity_segment'])})")
        if "tenure_segment" in rule:
            conds.append(f"tenure_segment IN ({sql_list(rule['tenure_segment'])})")
        if "flags_any" in rule:
            conds.append("(" + " OR ".join(FLAG_COLUMNS[f] for f in rule["flags_any"]) + ")")
        whens.append((" AND ".join(conds) or "TRUE", rule["cohort"], i, rule["reason"]))
    cohort = "CASE " + " ".join(f"WHEN {c} THEN '{k}'" for c, k, _, _ in whens) + f" ELSE '{pc['default_cohort']}' END"
    num = "CASE " + " ".join(f"WHEN {c} THEN {i}" for c, _, i, _ in whens) + " ELSE NULL END"
    reason = "CASE " + " ".join(f"WHEN {c} THEN '{r}'" for c, _, _, r in whens) + " ELSE 'no rule matched' END"
    return f"{cohort} AS priority_cohort, {num} AS priority_cohort_rule, {reason} AS priority_cohort_reason"


def main() -> None:
    cfg = tomllib.loads(CONFIG.read_text())
    t_start = time.time()
    if OUT_DB.exists():
        OUT_DB.unlink()
    con = duckdb.connect(str(OUT_DB))
    tmp = ROOT / "data" / "duckdb_tmp"
    con.execute(f"SET memory_limit='4GB'; SET temp_directory='{tmp}'; SET preserve_insertion_order=false; "
                f"SET TimeZone='UTC'; SET threads=3;")
    con.execute(f"ATTACH '{ODD_DB}' AS odd (READ_ONLY)")

    snap_id, snap_date, raw_file = con.execute(
        "SELECT source_snapshot_id, source_snapshot_date, source_file FROM odd._odd_lineage "
        "WHERE table_name='developer_activities'").fetchone()
    as_of = date.fromisoformat(con.execute(
        f"SELECT max(stats_max_value) FROM parquet_metadata('{raw_file}') WHERE path_in_schema='day'").fetchone()[0])
    a, t, ident = cfg["activity"], cfg["tenure"], cfg["identity"]
    win_start = as_of - timedelta(days=a["window_days"] - 1)
    min_date = t["min_valid_commit_date"]
    tables_used: set[str] = set()

    def step(name: str, sql: str, uses=()):
        t0 = time.time()
        con.execute(sql)
        tables_used.update(uses)
        print(f"  {name:38s} {time.time() - t0:6.0f}s", flush=True)

    print(f"snapshot {snap_id}, as-of {as_of}, window {win_start}..{as_of}", flush=True)

    # ---------------------------------------------------------------- per-developer identity facts
    agent_like = " OR ".join(f"email_norm LIKE '{p}'" for p in ident["ai_agent_email_patterns"])
    step("dev_stats", f"""
        CREATE TEMP TABLE dev_stats AS
        SELECT canonical_developer_id AS dev,
               sum(n_commits) AS n_commits, sum(n_bot_commits) AS n_bot_commits,
               sum(n_commits) FILTER (WHERE {agent_like}) AS n_agent_commits,
               sum(n_commits_bad_date) AS n_bad_date,
               min(first_seen_at) AS first_seen_at, max(last_seen_at) AS last_seen_at
        FROM odd.dev_identity_variants GROUP BY 1""", ["dev_identity_variants"])

    # GitHub ids per developer: ODD node id + numeric id in noreply emails
    step("dev_gh_candidates", r"""
        CREATE TEMP TABLE dev_gh_candidates AS
        SELECT canonical_developer_id AS dev, github_user_id AS gh_id, NULL::VARCHAR AS login,
               'ODD_GITHUB_ID' AS src, github_account_type AS account_type, NULL::TIMESTAMPTZ AS last_seen_at
        FROM odd.dev_github_ids WHERE github_user_id IS NOT NULL
        UNION ALL
        SELECT canonical_developer_id,
               try_cast(regexp_extract(email_norm, '^([0-9]+)\+([^@]+)@users\.noreply\.github\.com$', 1) AS BIGINT),
               regexp_extract(email_norm, '^([0-9]+)\+([^@]+)@users\.noreply\.github\.com$', 2),
               'NOREPLY', CASE WHEN email_norm LIKE '%[bot]@%' THEN 'Bot' ELSE 'User' END, last_seen_at
        FROM odd.dev_identity_variants
        WHERE regexp_full_match(email_norm, '^([0-9]+)\+([^@]+)@users\.noreply\.github\.com$')""",
         ["dev_github_ids"])
    step("dev_gh", f"""
        CREATE TEMP TABLE dev_gh AS
        SELECT dev,
               count(DISTINCT gh_id) AS n_gh_ids,
               min(gh_id) AS gh_id,
               list(DISTINCT gh_id ORDER BY gh_id) AS gh_ids,
               bool_or(src = 'ODD_GITHUB_ID') AS has_odd_id,
               bool_or(src = 'NOREPLY') AS has_noreply_id,
               bool_or(account_type = 'Bot') AS is_bot_account,
               arg_max(login, last_seen_at) FILTER (WHERE login IS NOT NULL) AS noreply_login
        FROM dev_gh_candidates WHERE gh_id > 0 GROUP BY 1""")
    # login-only noreply emails ('login@users.noreply.github.com', no numeric id)
    step("dev_login_only", r"""
        CREATE TEMP TABLE dev_login_only AS
        SELECT canonical_developer_id AS dev,
               arg_max(regexp_extract(email_norm, '^([^@+]+)@users\.noreply\.github\.com$', 1), last_seen_at) AS login
        FROM odd.dev_identity_variants
        WHERE regexp_full_match(email_norm, '^[^@+]+@users\.noreply\.github\.com$') GROUP BY 1""")

    # ---------------------------------------------------------------- identity linking -> persons
    step("all_devs", f"""
        CREATE TEMP TABLE all_devs AS
        SELECT d.dev,
               coalesce(s.n_commits, 0) AS n_commits,
               coalesce(s.n_bot_commits, 0) AS n_bot_commits,
               coalesce(s.n_agent_commits, 0) AS n_agent_commits,
               g.n_gh_ids, g.gh_id, g.gh_ids, g.has_odd_id, g.has_noreply_id, g.noreply_login,
               coalesce(g.is_bot_account, false) AS is_bot_account,
               coalesce(s.n_commits, 0) > 0 AND (
                   coalesce(s.n_bot_commits, 0) >= {ident['bot_commit_share_flag']} * s.n_commits
                   OR coalesce(s.n_agent_commits, 0) >= {ident['ai_agent_commit_share']} * s.n_commits) AS bot_by_commits
        FROM (SELECT id AS dev FROM odd.canonical_developers
              UNION SELECT dev FROM dev_stats) d
        LEFT JOIN dev_stats s USING (dev) LEFT JOIN dev_gh g USING (dev)""", ["canonical_developers"])
    step("gh_link_sizes", f"""
        CREATE TEMP TABLE linkable AS
        SELECT dev, gh_id FROM all_devs
        WHERE n_gh_ids = 1 AND NOT is_bot_account AND NOT bot_by_commits;
        CREATE TEMP TABLE gh_sizes AS SELECT gh_id, count(*) AS n FROM linkable GROUP BY 1""")
    step("members", f"""
        CREATE TABLE talent_seed_members AS
        SELECT CASE WHEN l.dev IS NOT NULL AND gs.n <= {cfg['linking']['max_devs_per_github_id']}
                    THEN 'gh:' || l.gh_id ELSE 'odd:' || d.dev END AS person_id,
               CASE WHEN l.dev IS NOT NULL AND gs.n <= {cfg['linking']['max_devs_per_github_id']}
                    THEN -l.gh_id ELSE d.dev END::BIGINT AS person_key,
               d.dev AS canonical_developer_id,
               CASE WHEN l.dev IS NOT NULL AND gs.n BETWEEN 2 AND {cfg['linking']['max_devs_per_github_id']}
                    THEN 'SAME_GITHUB_USER_ID' ELSE 'SINGLE_ID' END AS link_method,
               d.n_commits,
               '{snap_id}' AS source_snapshot_id, DATE '{snap_date}' AS source_snapshot_date,
               ['canonical_developers', 'dev_github_ids', 'dev_identity_variants'] AS source_tables
        FROM all_devs d LEFT JOIN linkable l USING (dev) LEFT JOIN gh_sizes gs ON gs.gh_id = l.gh_id""")

    # ---------------------------------------------------------------- activity (with commits fallback)
    step("dev_in_activity", "CREATE TEMP TABLE da_devs AS SELECT DISTINCT canonical_developer_id AS dev FROM odd.developer_activities",
         ["developer_activities"])
    step("gap_devs", "CREATE TEMP TABLE gap_devs AS SELECT dev FROM dev_stats WHERE n_commits > 0 "
                     "AND dev NOT IN (SELECT dev FROM da_devs)")
    if cfg["activity_fallback"]["enabled"]:
        step("fallback_from_commits (22 GB scan)", f"""
            CREATE TEMP TABLE fallback_activity AS
            SELECT c.repo_id, c.authored_at::DATE AS day, c.canonical_developer_id, count(*)::UBIGINT AS num_commits
            FROM odd.commits c SEMI JOIN gap_devs g ON g.dev = c.canonical_developer_id
            WHERE c.authored_at BETWEEN TIMESTAMPTZ '{min_date}' AND TIMESTAMPTZ '{as_of}' + INTERVAL 1 DAY
            GROUP BY ALL""", ["commits"])
    else:
        con.execute("CREATE TEMP TABLE fallback_activity AS SELECT * FROM odd.developer_activities LIMIT 0")
    con.execute("""CREATE TEMP VIEW act AS
        SELECT repo_id, day, canonical_developer_id, num_commits FROM odd.developer_activities
        UNION ALL SELECT repo_id, day, canonical_developer_id, num_commits FROM fallback_activity""")

    step("person_keys", f"""
        CREATE TEMP TABLE pmap AS SELECT DISTINCT person_key, person_id FROM talent_seed_members;
        CREATE TEMP TABLE member_keys AS SELECT canonical_developer_id, person_key FROM talent_seed_members;
        CREATE TEMP VIEW prd AS
        SELECT m.person_key, a.repo_id, a.day, a.num_commits::BIGINT AS commits
        FROM act a JOIN member_keys m ON m.canonical_developer_id = a.canonical_developer_id""")
    inh = cfg["repos"]["inherited_history_share"]
    # Aggregate person x repo in batches of person_key: a single 100M-row DISTINCT aggregation does not
    # fit in 4 GB on this VM.
    n_batches = 16
    # repo facts: creation date and whether the repo is tagged to a real crypto ecosystem
    con.execute("""CREATE TEMP TABLE repo_created AS
        SELECT r.id AS repo_id, r.repo_created_at::DATE AS created,
               r.id IN (SELECT er.repo_id FROM odd.ecosystems_repos er JOIN odd.ecosystems e ON e.id = er.ecosystem_id
                        WHERE e.is_crypto = 1 AND e.is_category = 0 AND e.is_virtual = 0) AS is_crypto
        FROM odd.repos r""")
    con.execute("""CREATE TEMP TABLE repos_agg (person_key BIGINT, repo_id INTEGER, commits BIGINT, active_days BIGINT,
                   first_active_date DATE, last_active_date DATE, commits_before_repo_created BIGINT,
                   is_crypto_repo BOOLEAN, first_original_date DATE, last_original_date DATE)""")
    t0 = time.time()
    for k in range(n_batches):
        con.execute(f"""
            INSERT INTO repos_agg
            SELECT p.person_key, p.repo_id, sum(p.commits)::BIGINT, count(DISTINCT p.day),
                   min(p.day), max(p.day),
                   coalesce(sum(p.commits) FILTER (WHERE p.day < rc.created), 0)::BIGINT,
                   coalesce(bool_or(rc.is_crypto), false),
                   min(p.day) FILTER (WHERE rc.created IS NULL OR p.day >= rc.created),
                   max(p.day) FILTER (WHERE rc.created IS NULL OR p.day >= rc.created)
            FROM prd p LEFT JOIN repo_created rc USING (repo_id)
            WHERE abs(p.person_key) % {n_batches} = {k}
            GROUP BY p.person_key, p.repo_id""")
    print(f"  {'person x repo aggregation (16 batches)':38s} {time.time() - t0:6.0f}s", flush=True)
    tables_used.add("repos")
    step("talent_seed_repos", f"""
        CREATE TABLE talent_seed_repos AS
        SELECT pm.person_id, a.repo_id, r.name AS repo_name, r.link AS repo_url,
               a.commits, a.active_days, a.first_active_date, a.last_active_date, a.commits_before_repo_created,
               a.commits_before_repo_created >= {inh} * a.commits AS inherited_history,
               a.is_crypto_repo, a.first_original_date, a.last_original_date,
               r.num_stars, r.is_blacklist,
               '{snap_id}' AS source_snapshot_id, DATE '{snap_date}' AS source_snapshot_date,
               ['developer_activities', 'commits', 'repos'] AS source_tables
        FROM repos_agg a JOIN pmap pm USING (person_key) LEFT JOIN odd.repos r ON r.id = a.repo_id""")
    con.execute("DROP TABLE repos_agg; DROP TABLE dev_gh_candidates;")
    original_only = cfg["population"]["original_crypto_work_only"]
    original_filter = ("AND rc.is_crypto AND (rc.created IS NULL OR p.day >= rc.created)" if original_only else "")
    step("window_activity", f"""
        CREATE TEMP TABLE wdays AS SELECT DISTINCT p.person_key, p.day FROM prd p LEFT JOIN repo_created rc USING (repo_id)
            WHERE p.day BETWEEN DATE '{win_start}' AND DATE '{as_of}' {original_filter};
        CREATE TEMP TABLE wstats AS
        SELECT pm.person_id, a.n_window_days, a.max_days_28
        FROM (SELECT person_key, count(*) AS n_window_days, max(n28) AS max_days_28
              FROM (SELECT x.person_key, x.day, count(*) AS n28 FROM wdays x JOIN wdays y
                      ON y.person_key = x.person_key AND y.day BETWEEN x.day AND x.day + {a['full_time_subwindow_days'] - 1}
                    GROUP BY ALL)
              GROUP BY 1) a JOIN pmap pm USING (person_key)""")

    # ---------------------------------------------------------------- ecosystems
    crypto = "AND e.is_crypto = 1" if cfg["population"]["require_is_crypto"] else ""
    step("root_chains", """
        CREATE TEMP TABLE root_chains AS
        SELECT e.id, e.name FROM odd.ecosystems e WHERE e.is_chain = 1 AND NOT EXISTS (
          SELECT 1 FROM odd.ecosystems_child_ecosystems_recursive r JOIN odd.ecosystems p ON p.id = r.parent_id
          WHERE r.child_id = e.id AND p.is_chain = 1)""", ["ecosystems", "ecosystems_child_ecosystems_recursive"])
    step("repo_ecosystem_map", f"""
        CREATE TEMP TABLE repo_tags AS
        SELECT er.repo_id, e.id AS ecosystem_id, e.name, e.is_chain
        FROM odd.ecosystems_repos er JOIN odd.ecosystems e ON e.id = er.ecosystem_id
        WHERE e.is_category = 0 AND e.is_virtual = 0 {crypto}
          AND er.repo_id IN (SELECT DISTINCT repo_id FROM talent_seed_repos);
        CREATE TEMP TABLE eco_roots AS
        SELECT DISTINCT t.ecosystem_id, rc.id AS root_id, rc.name AS root_name
        FROM (SELECT DISTINCT ecosystem_id FROM repo_tags) t
        JOIN (SELECT id AS child_id, id AS parent_id FROM root_chains
              UNION SELECT child_id, parent_id FROM odd.ecosystems_child_ecosystems_recursive) x ON x.child_id = t.ecosystem_id
        JOIN root_chains rc ON rc.id = x.parent_id;
        CREATE TEMP TABLE repo_eco AS
        SELECT repo_id, ecosystem_id, name AS ecosystem_name, 'SUB_ECOSYSTEM' AS level FROM repo_tags WHERE is_chain = 0
        UNION
        SELECT t.repo_id, r.root_id, r.root_name, 'TOP_LEVEL' FROM repo_tags t JOIN eco_roots r USING (ecosystem_id)""",
         ["ecosystems_repos"])
    step("talent_seed_ecosystems", f"""
        CREATE TABLE talent_seed_ecosystems AS
        SELECT r.person_id, x.level, x.ecosystem_id, x.ecosystem_name,
               count(*) AS repo_count, sum(r.commits)::BIGINT AS commits,
               count(*) FILTER (WHERE NOT r.inherited_history) AS repo_count_excluding_inherited,
               max(r.last_active_date) AS last_active_date,
               '{snap_id}' AS source_snapshot_id, DATE '{snap_date}' AS source_snapshot_date,
               ['ecosystems', 'ecosystems_repos', 'ecosystems_child_ecosystems_recursive', 'developer_activities'] AS source_tables
        FROM talent_seed_repos r JOIN repo_eco x USING (repo_id)
        GROUP BY ALL""")

    # ---------------------------------------------------------------- ODD per-developer fields
    step("odd_exclusivity (3.3 GB scan)", f"""
        CREATE TEMP TABLE excl AS
        SELECT m.person_id, count(*) AS eco_days, count(*) FILTER (WHERE e.is_exclusive) AS exclusive_eco_days
        FROM odd.eco_developer_activities e
        JOIN talent_seed_members m ON m.canonical_developer_id = e.canonical_developer_id
        WHERE e.day BETWEEN DATE '{win_start}' AND DATE '{as_of}' AND e.ecosystem_id IN (SELECT id FROM root_chains)
        GROUP BY 1""", ["eco_developer_activities"])
    step("odd_contribution_rank_asof (2.6 GB scan)", f"""
        CREATE TEMP TABLE odd_rank AS
        SELECT m.person_id,
               CASE max(CASE r.contribution_rank WHEN 'full_time' THEN 3 WHEN 'part_time' THEN 2 WHEN 'one_time' THEN 1 END)
                    WHEN 3 THEN 'full_time' WHEN 2 THEN 'part_time' WHEN 1 THEN 'one_time' END AS odd_contribution_rank_asof
        FROM odd.eco_developer_contribution_ranks r
        JOIN talent_seed_members m ON m.canonical_developer_id = r.canonical_developer_id
        WHERE r.day = DATE '{as_of}' AND r.ecosystem_id IN (SELECT id FROM root_chains)
        GROUP BY 1""", ["eco_developer_contribution_ranks"])

    # ---------------------------------------------------------------- contact points
    step("talent_seed_contact_points", f"""
        CREATE TEMP TABLE email_devs AS SELECT email_norm, count(DISTINCT canonical_developer_id) AS n_devs
            FROM odd.dev_identity_variants GROUP BY 1;
        CREATE TABLE talent_seed_contact_points AS
        SELECT m.person_id, 'EMAIL' AS type, v.email_norm AS value_normalized,
               arg_max(v.commit_author_email, v.n_commits) AS value,
               'UNVERIFIED' AS email_status,
               v.email_norm LIKE '%@users.noreply.github.com' AS is_github_noreply,
               ed.n_devs AS shared_by_n_developers,
               ed.n_devs >= {ident['placeholder_email_min_devs']} AS is_placeholder,
               list(DISTINCT v.commit_author_name ORDER BY v.commit_author_name) AS author_names,
               min(v.first_seen_at) AS first_seen_at, max(v.last_seen_at) AS last_seen_at,
               sum(v.n_commits)::BIGINT AS n_commits,
               '{snap_id}' AS source_snapshot_id, DATE '{snap_date}' AS source_snapshot_date,
               ['commits', 'dev_identity_variants'] AS source_tables
        FROM odd.dev_identity_variants v
        JOIN talent_seed_members m ON m.canonical_developer_id = v.canonical_developer_id
        JOIN email_devs ed USING (email_norm)
        WHERE v.email_norm <> ''
        GROUP BY m.person_id, v.email_norm, ed.n_devs""")

    # ---------------------------------------------------------------- person-level aggregates
    step("person_identity", """
        CREATE TEMP TABLE person_ident AS
        SELECT m.person_id,
               list(m.canonical_developer_id ORDER BY m.canonical_developer_id) AS canonical_developer_ids,
               count(*) AS n_canonical_ids,
               arg_max(m.canonical_developer_id, m.n_commits) AS primary_canonical_developer_id,
               sum(d.n_commits)::BIGINT AS commit_count, sum(d.n_bot_commits)::BIGINT AS commit_count_bot,
               sum(d.n_agent_commits)::BIGINT AS commit_count_ai_agent,
               bool_or(d.is_bot_account) AS any_bot_account,
               bool_or(d.n_gh_ids > 1) AS any_gh_conflict,
               max(d.gh_id) FILTER (WHERE d.n_gh_ids = 1) AS gh_id,
               bool_or(d.has_odd_id AND d.n_gh_ids = 1) AS gh_from_odd,
               bool_or(d.has_noreply_id AND d.n_gh_ids = 1) AS gh_from_noreply,
               max(d.noreply_login) FILTER (WHERE d.n_gh_ids = 1) AS noreply_login
        FROM talent_seed_members m JOIN all_devs d ON d.dev = m.canonical_developer_id
        GROUP BY 1""")
    step("person_names_dates", f"""
        CREATE TEMP TABLE person_names AS
        SELECT person_id, arg_max(commit_author_name, n) AS display_name, count(*) AS n_names
        FROM (SELECT m.person_id, v.commit_author_name, sum(v.n_commits) AS n
              FROM odd.dev_identity_variants v JOIN talent_seed_members m ON m.canonical_developer_id = v.canonical_developer_id
              GROUP BY ALL) GROUP BY 1;
        CREATE TEMP TABLE person_dates AS
        SELECT m.person_id, min(s.first_seen_at) AS first_seen_at, max(s.last_seen_at) AS last_seen_at,
               sum(s.n_bad_date)::BIGINT AS n_bad_date
        FROM talent_seed_members m JOIN dev_stats s ON s.dev = m.canonical_developer_id GROUP BY 1;
        CREATE TEMP TABLE person_login_only AS
        SELECT m.person_id, max(l.login) AS login FROM talent_seed_members m JOIN dev_login_only l ON l.dev = m.canonical_developer_id GROUP BY 1;
        CREATE TEMP TABLE person_gap AS
        SELECT DISTINCT m.person_id FROM talent_seed_members m JOIN gap_devs g ON g.dev = m.canonical_developer_id;
        CREATE TEMP TABLE person_repo_stats AS
        SELECT person_id, count(*) AS repository_count, count(*) FILTER (WHERE NOT inherited_history) AS repository_count_excluding_inherited,
               sum(commits) FILTER (WHERE NOT inherited_history)::BIGINT AS commit_count_excluding_inherited,
               max(last_active_date) AS last_active_date,
               min(first_original_date) FILTER (WHERE is_crypto_repo) AS first_crypto_commit_date,
               max(last_original_date) FILTER (WHERE is_crypto_repo) AS last_crypto_activity_date
        FROM talent_seed_repos GROUP BY 1;
        CREATE TEMP TABLE person_eco_stats AS
        SELECT person_id,
               count(*) FILTER (WHERE level = 'TOP_LEVEL') AS ecosystem_count,
               count(*) FILTER (WHERE level = 'TOP_LEVEL' AND repo_count_excluding_inherited > 0) AS ecosystem_count_excluding_inherited,
               count(*) FILTER (WHERE level = 'SUB_ECOSYSTEM') AS sub_ecosystem_count,
               list(ecosystem_name ORDER BY commits DESC) FILTER (WHERE level = 'TOP_LEVEL') AS top_level_ecosystems,
               list(ecosystem_name ORDER BY last_active_date DESC) FILTER (WHERE level = 'TOP_LEVEL' AND last_active_date >= DATE '{win_start}') AS top_level_ecosystems_in_window
        FROM talent_seed_ecosystems GROUP BY 1;
        CREATE TEMP TABLE person_loc AS
        SELECT m.person_id, arg_max(l.formatted_address, m.n_commits) AS location, arg_max(l.country, m.n_commits) AS country
        FROM talent_seed_members m JOIN odd.canonical_developer_locations l ON l.canonical_developer_id = m.canonical_developer_id
        GROUP BY 1;
        CREATE TEMP TABLE person_candidate_sha AS
        SELECT m.person_id, arg_max(v.latest_sha1, v.n_commits) AS sha, arg_max(r.name, v.n_commits) AS repo
        FROM odd.dev_identity_variants v JOIN talent_seed_members m ON m.canonical_developer_id = v.canonical_developer_id
        LEFT JOIN odd.repos r ON r.id = v.latest_sha1_repo_id
        WHERE v.n_bot_commits < v.n_commits GROUP BY 1""", ["canonical_developer_locations"])

    # ---------------------------------------------------------------- talent_seed
    bot_re = "|".join(f"(?:{p})" for p in ident["bot_name_patterns"]).replace("'", "''")
    step("talent_seed", f"""
        CREATE TABLE talent_seed AS
        WITH base AS (
          SELECT i.person_id, i.primary_canonical_developer_id, i.canonical_developer_ids, i.n_canonical_ids,
                 n.display_name, n.n_names,
                 i.gh_id AS github_user_id,
                 coalesce(i.noreply_login, lo.login) AS github_login,
                 CASE WHEN i.noreply_login IS NOT NULL THEN 'NOREPLY_ID_EMAIL'
                      WHEN lo.login IS NOT NULL THEN 'NOREPLY_LOGIN_EMAIL' END AS github_login_source,
                 CASE WHEN i.gh_from_noreply THEN 'NOREPLY' WHEN i.gh_from_odd THEN 'ODD_GITHUB_ID'
                      WHEN lo.login IS NOT NULL THEN 'NOREPLY' ELSE 'UNRESOLVED' END AS github_resolution_method,
                 i.gh_from_odd AS github_corroborated_by_odd_id,
                 CASE WHEN i.any_gh_conflict THEN NULL WHEN i.gh_id IS NULL THEN c.sha END AS github_candidate_commit_sha,
                 CASE WHEN i.any_gh_conflict THEN NULL WHEN i.gh_id IS NULL THEN c.repo END AS github_candidate_repo,
                 pl.location, pl.country,
                 pd.first_seen_at::DATE AS first_commit_date,
                 rs.first_crypto_commit_date, rs.last_crypto_activity_date,
                 coalesce(rs.last_active_date, pd.last_seen_at::DATE) AS last_activity_date,
                 coalesce(rs.repository_count, 0) AS repository_count,
                 coalesce(rs.repository_count_excluding_inherited, 0) AS repository_count_excluding_inherited,
                 coalesce(es.ecosystem_count, 0) AS ecosystem_count,
                 coalesce(es.ecosystem_count_excluding_inherited, 0) AS ecosystem_count_excluding_inherited,
                 coalesce(es.sub_ecosystem_count, 0) AS sub_ecosystem_count,
                 coalesce(es.top_level_ecosystems, []) AS top_level_ecosystems,
                 i.commit_count, i.commit_count_bot, i.commit_count_ai_agent,
                 coalesce(rs.commit_count_excluding_inherited, 0) AS commit_count_excluding_inherited,
                 (DATE '{as_of}' - {"rs.first_crypto_commit_date" if original_only else "pd.first_seen_at::DATE"}) AS tenure_days,
                 coalesce(w.n_window_days, 0) AS active_days_in_window,
                 coalesce(w.max_days_28, 0) AS max_active_days_in_28d,
                 coalesce(x.eco_days, 0) AS exclusivity_eco_days, coalesce(x.exclusive_eco_days, 0) AS exclusivity_exclusive_days,
                 coalesce(es.top_level_ecosystems_in_window, []) AS top_level_ecosystems_in_window,
                 rk.odd_contribution_rank_asof,
                 (i.any_bot_account OR i.commit_count_bot >= {ident['bot_commit_share_flag']} * i.commit_count
                    OR i.commit_count_ai_agent >= {ident['ai_agent_commit_share']} * i.commit_count) AND i.commit_count > 0
                    OR coalesce(i.any_bot_account, false)
                    OR regexp_matches(lower(coalesce(n.display_name, '')), '{bot_re}')
                    OR regexp_matches(lower(coalesce(i.noreply_login, lo.login, '')), '{bot_re}') AS flag_probable_bot,
                 coalesce(i.any_gh_conflict, false) AS flag_github_conflict,
                 i.n_canonical_ids > 1 AS flag_linked_ids,
                 g.person_id IS NOT NULL AS flag_activity_table_gap,
                 coalesce(pd.n_bad_date, 0) > 0 AS flag_bad_commit_dates
          FROM person_ident i
          LEFT JOIN person_names n USING (person_id) LEFT JOIN person_dates pd USING (person_id)
          LEFT JOIN person_login_only lo USING (person_id) LEFT JOIN person_candidate_sha c USING (person_id)
          LEFT JOIN person_loc pl USING (person_id) LEFT JOIN person_repo_stats rs USING (person_id)
          LEFT JOIN person_eco_stats es USING (person_id) LEFT JOIN wstats w USING (person_id)
          LEFT JOIN excl x USING (person_id) LEFT JOIN odd_rank rk USING (person_id)
          LEFT JOIN person_gap g USING (person_id)
        ), seg AS (
          SELECT *,
                 CASE WHEN github_resolution_method = 'UNRESOLVED' THEN 'NONE'
                      WHEN flag_github_conflict THEN '{cfg['github_confidence']['conflict_downgrades_to']}'
                      WHEN github_corroborated_by_odd_id THEN 'HIGH'
                      WHEN github_user_id IS NOT NULL THEN 'MEDIUM' ELSE 'LOW' END AS github_confidence,
                 CASE WHEN tenure_days IS NULL THEN 'UNKNOWN' WHEN tenure_days <= {t['newcomer_max_days']} THEN 'NEWCOMER'
                      WHEN tenure_days <= {t['emerging_max_days']} THEN 'EMERGING' ELSE 'ESTABLISHED' END AS tenure_segment,
                 CASE WHEN active_days_in_window = 0 THEN 'UNKNOWN'
                      WHEN max_active_days_in_28d >= {a['full_time_min_days_in_28d']} THEN 'FULL_TIME'
                      WHEN active_days_in_window >= {a['part_time_min_active_days']} THEN 'PART_TIME' ELSE 'ONE_TIME' END AS activity_segment,
                 CASE WHEN exclusivity_eco_days > 0 THEN
                           CASE WHEN exclusivity_exclusive_days = exclusivity_eco_days THEN 'EXCLUSIVE' ELSE 'MULTICHAIN' END
                      WHEN len(top_level_ecosystems_in_window) = 1 THEN 'EXCLUSIVE'
                      WHEN len(top_level_ecosystems_in_window) > 1 THEN 'MULTICHAIN'
                      ELSE 'UNKNOWN' END AS exclusivity,
                 CASE WHEN exclusivity_eco_days > 0 THEN 'ODD_IS_EXCLUSIVE'
                      WHEN len(top_level_ecosystems_in_window) > 0 THEN 'TOP_LEVEL_COUNT_FALLBACK'
                      ELSE 'NO_CHAIN_ACTIVITY_IN_WINDOW' END AS exclusivity_method,
                 len(top_level_ecosystems_in_window) AS distinct_top_level_ecosystems_in_window
          FROM base
        )
        SELECT *, {cohort_case(cfg)},
               '{cfg['priority_cohort']['status']}' AS priority_cohort_status,
               DATE '{as_of}' AS as_of_activity_date, DATE '{win_start}' AS activity_window_start,
               '{snap_id}' AS source_snapshot_id, DATE '{snap_date}' AS source_snapshot_date,
               [{sql_list(sorted(tables_used))}] AS source_tables
        FROM seg""")

    # ---------------------------------------------------------------- run record + exports
    counts = {tbl: con.execute(f"SELECT count(*) FROM {tbl}").fetchone()[0] for tbl in
              ("talent_seed", "talent_seed_members", "talent_seed_contact_points", "talent_seed_repos", "talent_seed_ecosystems")}
    con.execute("""CREATE TABLE talent_seed_runs (run_at TIMESTAMPTZ, source_snapshot_id VARCHAR, source_snapshot_date DATE,
                   as_of_activity_date DATE, config_toml VARCHAR, row_counts JSON, build_seconds DOUBLE, attribution VARCHAR)""")
    con.execute("INSERT INTO talent_seed_runs VALUES (?,?,?,?,?,?,?,?)",
                [datetime.now(timezone.utc), snap_id, snap_date, as_of, CONFIG.read_text(), json.dumps(counts),
                 time.time() - t_start,
                 "Data from Electric Capital Open Dev Data (https://opendevdata.org), licensed CC BY 4.0."])
    out_dir = ROOT / "exports" / snap_id
    out_dir.mkdir(parents=True, exist_ok=True)
    for tbl in list(counts) + ["talent_seed_runs"]:
        con.execute(f"COPY {tbl} TO '{out_dir / (tbl + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
    con.close()
    print(json.dumps(counts, indent=1))
    print(f"done in {time.time() - t_start:.0f}s -> {OUT_DB}, {out_dir}")


if __name__ == "__main__":
    main()
