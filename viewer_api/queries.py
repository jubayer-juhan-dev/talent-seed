"""SQL for the viewer API, moved from scripts/seed_viewer/server.py.

One change: every ORDER BY now has a tiebreaker, so the same request always returns the same order
(the old server returned tied rows, and the export's best email, in a different order on each call).

Each api_* function takes a read-only DuckDB connection and q, a dict of query-string lists
(as urllib.parse.parse_qs returns), and returns plain dicts. main.py turns typed FastAPI
parameters into q, so the results are the same as before.
"""

import csv
import datetime
import decimal
import io
import re

import duckdb

from .logins import add_logins, looked_up
from .settings import ATTRIBUTION, DB, EXPORT_LIMIT, PAGE_SIZE

SORTS = {"commits": "commit_count", "last_activity": "last_activity_date", "first_commit": "first_commit_date",
         "repos": "repository_count", "ecosystems": "ecosystem_count", "active_days": "active_days_in_window",
         "name": "display_name"}
LIST_COLS = """person_id, display_name, github_login, github_user_id, github_confidence, country,
    priority_cohort, priority_cohort_reason, tenure_segment, activity_segment, exclusivity,
    active_days_in_window, commit_count, repository_count, ecosystem_count, top_level_ecosystems,
    first_commit_date, last_activity_date, flag_probable_bot, flag_linked_ids, flag_activity_table_gap,
    flag_github_conflict"""


def jsonable(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def query(con, sql, params=()):
    rel = con.execute(sql, list(params))
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def connect():
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET TimeZone='UTC'; SET threads=2;")
    return con


def api_meta(con, _q):
    run = query(con, "SELECT run_at, source_snapshot_id, source_snapshot_date, as_of_activity_date, row_counts "
                     "FROM talent_seed_runs ORDER BY run_at DESC LIMIT 1")[0]
    cohorts = query(con, "SELECT priority_cohort AS k, count(*) AS n FROM talent_seed GROUP BY 1 ORDER BY 1")
    chains = query(con, """SELECT ecosystem_name AS k, count(*) AS n FROM talent_seed_ecosystems e
                           JOIN talent_seed t USING (person_id)
                           WHERE e.level = 'TOP_LEVEL' AND t.priority_cohort <> 'HOLD'
                           GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 60""")
    countries = query(con, """SELECT country AS k, count(*) AS n FROM talent_seed
                              WHERE country IS NOT NULL AND priority_cohort <> 'HOLD' GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 80""")
    return {"run": run, "cohorts": cohorts, "chains": chains, "countries": countries}


def one(q, name):
    return (q.get(name) or [""])[0].strip()


def build_filters(q):
    """WHERE clause and params shared by /api/people and /api/export.csv."""
    where, params = [], []
    for col, name in (("priority_cohort", "cohort"), ("activity_segment", "activity"),
                      ("tenure_segment", "tenure"), ("exclusivity", "exclusivity"), ("country", "country")):
        vals = [v for v in one(q, name).split(",") if v]
        if vals:
            where.append(f"{col} IN ({','.join('?' * len(vals))})")
            params += vals
    if one(q, "chain"):
        where.append("person_id IN (SELECT person_id FROM talent_seed_ecosystems WHERE level='TOP_LEVEL' AND ecosystem_name = ?)")
        params.append(one(q, "chain"))
    # eco: any ecosystem (chain or sub-ecosystem such as Uniswap); several names separated by "|" match any of them
    ecos = [v for v in one(q, "eco").split("|") if v]
    if ecos:
        where.append(f"person_id IN (SELECT person_id FROM talent_seed_ecosystems WHERE ecosystem_name IN ({','.join('?' * len(ecos))}))")
        params += ecos
    ids = [v for v in one(q, "ids").split(",") if re.fullmatch(r"(gh|odd):\d+", v)]
    if ids:
        where.append(f"person_id IN ({','.join('?' * len(ids))})")
        params += ids
    if one(q, "hide_flagged") == "1":
        where.append("NOT flag_probable_bot AND NOT flag_github_conflict")
    text = one(q, "q")
    if text:
        if "@" in text:
            where.append("person_id IN (SELECT person_id FROM talent_seed_contact_points WHERE value_normalized = ?)")
            params.append(text.lower())
        elif re.fullmatch(r"(gh|odd):\d+", text):
            where.append("person_id = ?")
            params.append(text)
        else:
            extra = [r[0] for r in looked_up("github_login LIKE ? LIMIT 500", [f"{text}%"])]
            where.append("(display_name ILIKE ? OR github_login ILIKE ?"
                         + (f" OR person_id IN ({','.join('?' * len(extra))})" if extra else "") + ")")
            params += [f"%{text}%", f"{text}%", *extra]
    sort = SORTS.get(one(q, "sort"), "active_days_in_window")
    direction = "ASC" if one(q, "dir") == "asc" else "DESC"
    w = ("WHERE " + " AND ".join(where)) if where else ""
    return w, params, f"ORDER BY {sort} {direction} NULLS LAST, person_id"


def api_people(con, q):
    w, params, order = build_filters(q)
    page = max(int(one(q, "page") or 1), 1)
    total = con.execute(f"SELECT count(*) FROM talent_seed {w}", params).fetchone()[0]
    rows = query(con, f"SELECT {LIST_COLS} FROM talent_seed {w} {order} "
                      f"LIMIT {PAGE_SIZE} OFFSET {(page - 1) * PAGE_SIZE}", params)
    return {"total": total, "page": page, "page_size": PAGE_SIZE, "rows": add_logins(rows)}


def api_overview(con, _q):
    """Aggregates for the overview tab. Everything except the cohort counts covers P1-P3 without bots/conflicts."""
    active = "priority_cohort <> 'HOLD' AND NOT flag_probable_bot AND NOT flag_github_conflict"
    return {
        "cohorts": query(con, "SELECT priority_cohort AS k, count(*) AS n FROM talent_seed GROUP BY 1 ORDER BY 1"),
        "chains": query(con, """SELECT e.ecosystem_name AS k, count(*) AS n,
                                    count(*) FILTER (WHERE t.priority_cohort = 'P1') AS p1
                                 FROM talent_seed_ecosystems e JOIN talent_seed t USING (person_id)
                                 WHERE e.level = 'TOP_LEVEL' AND t.priority_cohort <> 'HOLD'
                                   AND NOT t.flag_probable_bot AND NOT t.flag_github_conflict
                                 GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 20"""),
        "mix": query(con, f"""SELECT tenure_segment AS tenure, activity_segment AS activity, count(*) AS n
                              FROM talent_seed WHERE {active} GROUP BY 1, 2 ORDER BY 1, 2"""),
        "countries": query(con, f"""SELECT country AS k, count(*) AS n FROM talent_seed
                                    WHERE {active} AND country IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 10"""),
        "no_country": con.execute(f"SELECT count(*) FILTER (WHERE country IS NULL), count(*) FROM talent_seed WHERE {active}").fetchone(),
    }


def api_ecosystems(con, q):
    """Type-ahead over chains and sub-ecosystems, counting active (P1-P3) people in each."""
    text = one(q, "q")
    return {"rows": query(con, """SELECT e.ecosystem_name AS k, e.level, count(*) AS n
                                  FROM talent_seed_ecosystems e JOIN talent_seed t USING (person_id)
                                  WHERE t.priority_cohort <> 'HOLD' AND NOT t.flag_probable_bot AND e.ecosystem_name ILIKE ?
                                  GROUP BY 1, 2 ORDER BY (lower(e.ecosystem_name) LIKE lower(?)) DESC, n DESC, k LIMIT 12""",
                          [f"%{text}%", f"{text}%"])}


def export_csv(con, q):
    w, params, order = build_filters(q)
    rows = query(con, f"""
        WITH people AS (SELECT * FROM talent_seed {w} {order} LIMIT {EXPORT_LIMIT}),
        best AS (SELECT person_id, first(value ORDER BY n_commits DESC, value) AS email FROM talent_seed_contact_points
                 WHERE person_id IN (SELECT person_id FROM people) AND NOT is_github_noreply AND NOT is_placeholder
                 GROUP BY 1)
        SELECT p.person_id, p.display_name, p.github_login,
               CASE WHEN p.github_login IS NOT NULL THEN 'https://github.com/' || p.github_login END AS github_url,
               p.github_confidence, p.location, p.country, p.priority_cohort, p.priority_cohort_reason,
               p.priority_cohort_status AS cohort_status, p.activity_segment, p.tenure_segment, p.exclusivity,
               p.active_days_in_window AS active_days_last_84d, p.commit_count_excluding_inherited,
               array_to_string(p.top_level_ecosystems[1:5], '; ') AS top_chains, p.last_crypto_activity_date,
               b.email, CASE WHEN b.email IS NOT NULL THEN 'UNVERIFIED' END AS email_status,
               p.source_snapshot_id, p.as_of_activity_date, ? AS attribution
        FROM people p LEFT JOIN best b USING (person_id) {order.replace('ORDER BY ', 'ORDER BY p.').replace(', person_id', ', p.person_id')}""",
                 [*params, ATTRIBUTION])
    cols = list(rows[0].keys()) if rows else ["person_id"]  # before add_logins, which adds extra keys to some rows
    add_logins(rows)
    buf = io.StringIO()
    out = csv.writer(buf)
    out.writerow(cols)
    for r in rows:
        out.writerow(["" if r[c] is None else jsonable(r[c]) for c in cols])
    return buf.getvalue()


def api_person(con, q):
    pid = (q.get("id") or [""])[0]
    p = query(con, "SELECT * EXCLUDE (source_tables) , source_tables FROM talent_seed WHERE person_id = ?", [pid])
    if not p:
        return {"error": f"No person with id {pid}"}
    return {
        "person": add_logins(p)[0],
        "members": query(con, "SELECT canonical_developer_id, link_method, n_commits FROM talent_seed_members "
                              "WHERE person_id = ? ORDER BY n_commits DESC, canonical_developer_id", [pid]),
        "contacts": query(con, """SELECT value, email_status, is_github_noreply, is_placeholder, shared_by_n_developers,
                                  author_names, first_seen_at, last_seen_at, n_commits FROM talent_seed_contact_points
                                  WHERE person_id = ? ORDER BY n_commits DESC, value""", [pid]),
        "ecosystems": query(con, """SELECT level, ecosystem_name, repo_count, repo_count_excluding_inherited, commits,
                                    last_active_date FROM talent_seed_ecosystems WHERE person_id = ?
                                    ORDER BY level DESC, commits DESC, ecosystem_name LIMIT 60""", [pid]),
        "repos": query(con, """SELECT repo_name, repo_url, commits, active_days, first_active_date, last_active_date,
                               inherited_history, num_stars FROM talent_seed_repos WHERE person_id = ?
                               ORDER BY last_active_date DESC, repo_name LIMIT 100""", [pid]),
        "top_repos": query(con, """SELECT repo_name, repo_url, commits, active_days, first_original_date,
                                   last_original_date, num_stars FROM talent_seed_repos
                                   WHERE person_id = ? AND is_crypto_repo AND NOT inherited_history
                                   ORDER BY last_original_date >= (SELECT activity_window_start FROM talent_seed WHERE person_id = ?) DESC,
                                   active_days DESC, repo_name LIMIT 8""", [pid, pid]),
        "repo_total": con.execute("SELECT count(*) FROM talent_seed_repos WHERE person_id = ?", [pid]).fetchone()[0],
    }
