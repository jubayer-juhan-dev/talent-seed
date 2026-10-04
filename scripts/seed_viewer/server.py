"""Talent Seed viewer: a small local web app over data/talent_seed.duckdb.

Run:   uv run scripts/seed_viewer/server.py [--port 8765] [--host 127.0.0.1]
Open:  http://localhost:8765  (from another machine: ssh -L 8765:localhost:8765 root@<vm>)

Access key: if TALENT_SEED_KEY is set, every request needs it, as ?key=, an X-Access-Key header (the
page sends it on API calls) or the ts_key cookie (set when the page is opened with ?key=). The header
path means the link works even in browsers that drop cookies. Without the key it answers 401. This is a
stop-gap so a tunnelled link doesn't expose emails to anyone who finds it, not a real login.

Read-only. Each request opens its own read-only DuckDB connection and closes it, so the database
is never locked between requests and scripts/m4_build_talent_seed.py can rebuild it (the page then
shows "rebuilding" until the build finishes).
"""

import argparse
import csv
import datetime
import decimal
import hmac
import io
import json
import os
import re
import sqlite3
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "talent_seed.duckdb"
# GitHub logins found later by scripts/m5_lookup_github_logins.py; overlaid on talent_seed where it has none.
LOGINS = ROOT / "data" / "github_logins.sqlite"
INDEX = Path(__file__).with_name("index.html")
ACCESS_KEY = os.environ.get("TALENT_SEED_KEY", "")
KEY_COOKIE = "ts_key"
LOCKED_PAGE = b"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Talent Seed</title><body style="font:15px system-ui;display:grid;place-items:center;min-height:90vh;color:#555">
<p>This page needs its access link. Ask the owner for the full URL.</p></body>"""
PAGE_SIZE = 50
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


def looked_up(where_sql, params):
    """Rows from the login-lookup file (empty if the file doesn't exist yet). Read-only."""
    if not LOGINS.exists():
        return []
    db = sqlite3.connect(f"file:{LOGINS}?mode=ro", uri=True)
    try:
        return db.execute(f"SELECT person_id, github_login, github_user_id, method, looked_up_at FROM github_logins "
                          f"WHERE github_login IS NOT NULL AND {where_sql}", params).fetchall()
    finally:
        db.close()


def add_logins(rows):
    """Fill github_login (and github_url / github_user_id when present) from the lookup file, in place.
    COMMIT_API matches are MEDIUM confidence, as in inspect_developer.py."""
    need = [r["person_id"] for r in rows if not r.get("github_login")]
    found = {}
    for i in range(0, len(need), 900):  # SQLite parameter limit
        chunk = need[i:i + 900]
        found.update({pid: x for pid, *x in looked_up(f"person_id IN ({','.join('?' * len(chunk))})", chunk)})
    for r in rows:
        hit = found.get(r["person_id"])
        if not hit:
            continue
        login, uid, method, at = hit
        r["github_login"] = login
        r["github_login_source"] = "GITHUB_API_" + method
        r["github_login_looked_up_at"] = at
        if "github_url" in r:
            r["github_url"] = f"https://github.com/{login}"
        if "github_user_id" in r and r["github_user_id"] is None:
            r["github_user_id"] = uid
        if "github_confidence" in r and method == "COMMIT_API" and r["github_confidence"] in (None, "NONE", "LOW"):
            r["github_confidence"] = "MEDIUM"
    return rows


def api_meta(con, _q):
    run = query(con, "SELECT run_at, source_snapshot_id, source_snapshot_date, as_of_activity_date, row_counts "
                     "FROM talent_seed_runs ORDER BY run_at DESC LIMIT 1")[0]
    cohorts = query(con, "SELECT priority_cohort AS k, count(*) AS n FROM talent_seed GROUP BY 1 ORDER BY 1")
    chains = query(con, """SELECT ecosystem_name AS k, count(*) AS n FROM talent_seed_ecosystems e
                           JOIN talent_seed t USING (person_id)
                           WHERE e.level = 'TOP_LEVEL' AND t.priority_cohort <> 'HOLD'
                           GROUP BY 1 ORDER BY 2 DESC LIMIT 60""")
    countries = query(con, """SELECT country AS k, count(*) AS n FROM talent_seed
                              WHERE country IS NOT NULL AND priority_cohort <> 'HOLD' GROUP BY 1 ORDER BY 2 DESC LIMIT 80""")
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
                                 GROUP BY 1 ORDER BY 2 DESC LIMIT 20"""),
        "mix": query(con, f"""SELECT tenure_segment AS tenure, activity_segment AS activity, count(*) AS n
                              FROM talent_seed WHERE {active} GROUP BY 1, 2"""),
        "countries": query(con, f"""SELECT country AS k, count(*) AS n FROM talent_seed
                                    WHERE {active} AND country IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10"""),
        "no_country": con.execute(f"SELECT count(*) FILTER (WHERE country IS NULL), count(*) FROM talent_seed WHERE {active}").fetchone(),
    }


def api_ecosystems(con, q):
    """Type-ahead over chains and sub-ecosystems, counting active (P1-P3) people in each."""
    text = one(q, "q")
    return {"rows": query(con, """SELECT e.ecosystem_name AS k, e.level, count(*) AS n
                                  FROM talent_seed_ecosystems e JOIN talent_seed t USING (person_id)
                                  WHERE t.priority_cohort <> 'HOLD' AND NOT t.flag_probable_bot AND e.ecosystem_name ILIKE ?
                                  GROUP BY 1, 2 ORDER BY (lower(e.ecosystem_name) LIKE lower(?)) DESC, n DESC LIMIT 12""",
                          [f"%{text}%", f"{text}%"])}


EXPORT_LIMIT = 5000
ATTRIBUTION = "Data from Electric Capital Open Dev Data (opendevdata.org), CC BY 4.0"


def export_csv(con, q):
    w, params, order = build_filters(q)
    rows = query(con, f"""
        WITH people AS (SELECT * FROM talent_seed {w} {order} LIMIT {EXPORT_LIMIT}),
        best AS (SELECT person_id, arg_max(value, n_commits) AS email FROM talent_seed_contact_points
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
                              "WHERE person_id = ? ORDER BY n_commits DESC", [pid]),
        "contacts": query(con, """SELECT value, email_status, is_github_noreply, is_placeholder, shared_by_n_developers,
                                  author_names, first_seen_at, last_seen_at, n_commits FROM talent_seed_contact_points
                                  WHERE person_id = ? ORDER BY n_commits DESC""", [pid]),
        "ecosystems": query(con, """SELECT level, ecosystem_name, repo_count, repo_count_excluding_inherited, commits,
                                    last_active_date FROM talent_seed_ecosystems WHERE person_id = ?
                                    ORDER BY level DESC, commits DESC LIMIT 60""", [pid]),
        "repos": query(con, """SELECT repo_name, repo_url, commits, active_days, first_active_date, last_active_date,
                               inherited_history, num_stars FROM talent_seed_repos WHERE person_id = ?
                               ORDER BY last_active_date DESC LIMIT 100""", [pid]),
        "top_repos": query(con, """SELECT repo_name, repo_url, commits, active_days, first_original_date,
                                   last_original_date, num_stars FROM talent_seed_repos
                                   WHERE person_id = ? AND is_crypto_repo AND NOT inherited_history
                                   ORDER BY last_original_date >= (SELECT activity_window_start FROM talent_seed WHERE person_id = ?) DESC,
                                   active_days DESC LIMIT 8""", [pid, pid]),
        "repo_total": con.execute("SELECT count(*) FROM talent_seed_repos WHERE person_id = ?", [pid]).fetchone()[0],
    }


ROUTES = {"/api/meta": api_meta, "/api/people": api_people, "/api/person": api_person,
          "/api/overview": api_overview, "/api/ecosystems": api_ecosystems, "/api/export.csv": export_csv}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body: bytes, ctype, headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self, q):
        if not ACCESS_KEY:
            return True
        c = SimpleCookie(self.headers.get("Cookie", "")).get(KEY_COOKIE)
        given = [(q.get("key") or [""])[0], self.headers.get("X-Access-Key", ""), c.value if c else ""]
        return any(g and hmac.compare_digest(g.encode(), ACCESS_KEY.encode()) for g in given)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        if not self.authorized(q):
            if url.path.startswith("/api/"):
                return self.send(401, b'{"error":"Access link required"}', "application/json")
            return self.send(401, LOCKED_PAGE, "text/html; charset=utf-8")
        if url.path in ("/", "/index.html"):
            # Opened with ?key=: also set a cookie, so a later visit without the key still works.
            cookie = {"Set-Cookie": f"{KEY_COOKIE}={ACCESS_KEY}; Path=/; Max-Age=31536000; HttpOnly; Secure; SameSite=Lax"} \
                if ACCESS_KEY and "key" in q else None
            return self.send(200, INDEX.read_bytes(), "text/html; charset=utf-8", cookie)
        fn = ROUTES.get(url.path)
        if not fn:
            return self.send(404, b'{"error":"not found"}', "application/json")
        try:
            con = connect()
        except duckdb.IOException:
            return self.send(503, json.dumps({"error": "The database is being rebuilt. Try again in a few minutes."}).encode(),
                             "application/json")
        try:
            out = fn(con, q)
            if isinstance(out, str):  # CSV export
                return self.send(200, out.encode("utf-8-sig"), "text/csv; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="talent_seed_shortlist.csv"'})
            self.send(200, json.dumps(jsonable(out)).encode(), "application/json")
        except Exception as e:  # report to the page instead of dropping the connection
            self.send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode(), "application/json")
        finally:
            con.close()

    def log_message(self, fmt, *args):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    print(f"Talent Seed viewer on http://{a.host}:{a.port}  (database: {DB})", flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
