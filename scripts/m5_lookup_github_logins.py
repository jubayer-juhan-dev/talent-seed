"""Milestone 5: look up missing GitHub logins through the GitHub REST API.

Reads people with no github_login from data/talent_seed.duckdb (read-only) and writes what it finds to
a separate SQLite file, data/github_logins.sqlite, so the main database is never written and the
viewer can read results while this runs.

Per person (same order as inspect_developer.py):
  - github_user_id known  -> GET /user/{id}                        method USER_ID_API
  - otherwise             -> GET /repos/{repo}/commits/{sha}       method COMMIT_API (login only if the
                             commit's email is linked to an account)

Resumable: people already in the SQLite file are skipped, so re-running continues where it stopped.
Rate limits: stays below the hourly budget instead of sleeping. When X-RateLimit-Remaining falls to
--reserve it stops cleanly and says when to re-run (pass --wait to sleep until the reset instead).

Run:  uv run scripts/m5_lookup_github_logins.py --cohort P1
Token: GITHUB_TOKEN env var, else /root/.github_token.
"""

import argparse
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "talent_seed.duckdb"
OUT = ROOT / "data" / "github_logins.sqlite"
TOKEN_FILE = Path("/root/.github_token")

SCHEMA = """
CREATE TABLE IF NOT EXISTS github_logins (
    person_id       TEXT PRIMARY KEY,
    priority_cohort TEXT,
    method          TEXT NOT NULL,      -- USER_ID_API | COMMIT_API
    api_status      INTEGER,            -- 200 found, 404 deleted/unknown, 422 bad commit/repo, ...
    github_login    TEXT,               -- NULL when not found
    github_user_id  INTEGER,
    source_repo     TEXT,
    source_sha      TEXT,
    looked_up_at    TEXT NOT NULL
);
"""
FINAL = (200, 404, 409, 422, 451)  # answers that won't change on retry; anything else is retried next run


def log(msg):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}", flush=True)


def token():
    t = os.environ.get("GITHUB_TOKEN") or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not t:
        sys.exit("No GitHub token: set GITHUB_TOKEN or write it to /root/.github_token")
    return t


def todo(cohorts, done):
    con = duckdb.connect(str(DB), read_only=True)  # closed right away so a rebuild is never blocked
    try:
        rows = con.execute(f"""
            SELECT person_id, priority_cohort, github_user_id, github_candidate_repo, github_candidate_commit_sha
            FROM talent_seed
            WHERE github_login IS NULL AND priority_cohort IN ({','.join('?' * len(cohorts))})
              AND (github_user_id IS NOT NULL OR github_candidate_commit_sha IS NOT NULL)
            ORDER BY priority_cohort, active_days_in_window DESC, person_id""", cohorts).fetchall()
    finally:
        con.close()
    return [r for r in rows if r[0] not in done]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", default="P1", help="comma-separated, e.g. P1 or P1,P2")
    ap.add_argument("--reserve", type=int, default=100, help="stop when this many API calls remain this hour")
    ap.add_argument("--wait", action="store_true", help="sleep until the rate limit resets instead of stopping")
    a = ap.parse_args()
    cohorts = [c.strip().upper() for c in a.cohort.split(",") if c.strip()]

    out = sqlite3.connect(OUT)
    out.execute("PRAGMA journal_mode=WAL")  # the viewer reads while we write
    out.executescript(SCHEMA)
    done = {r[0] for r in out.execute(f"SELECT person_id FROM github_logins WHERE api_status IN ({','.join(map(str, FINAL))})")}
    work = todo(cohorts, done)
    log(f"cohorts {','.join(cohorts)}: {len(work)} people to look up ({len(done)} already done)")
    if not work:
        return

    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                      "User-Agent": "talent-seed-login-lookup", "Authorization": f"Bearer {token()}"})
    found = calls = 0
    t0 = time.time()
    for i, (pid, cohort, uid, repo, sha) in enumerate(work, 1):
        if uid is not None:
            method, path = "USER_ID_API", f"/user/{uid}"
        elif repo and sha:
            method, path = "COMMIT_API", f"/repos/{repo}/commits/{sha}"
        else:
            continue
        for attempt in range(4):
            try:
                r = s.get("https://api.github.com" + path, timeout=30)
            except requests.RequestException as e:  # network blip: back off briefly and retry
                log(f"  network error on {pid} ({e.__class__.__name__}); retry {attempt + 1}/3")
                time.sleep(5 * (attempt + 1))
                continue
            calls += 1
            if r.status_code in (403, 429) and ("Retry-After" in r.headers or r.headers.get("X-RateLimit-Remaining") == "0"):
                wait = int(r.headers.get("Retry-After") or max(int(r.headers.get("X-RateLimit-Reset", "0")) - time.time(), 1))
                if not a.wait:
                    log(f"rate limited; stopping. Re-run in {wait // 60 + 1} min to continue ({i - 1}/{len(work)} done)")
                    return
                log(f"rate limited; waiting {wait}s"); time.sleep(wait + 1)
                continue
            if r.status_code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            break
        else:
            log(f"  giving up on {pid} for this run (will retry next run)")
            continue

        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        login = gid = None
        if r.status_code == 200:
            acct = body if method == "USER_ID_API" else (body.get("author") or {})
            login, gid = acct.get("login"), acct.get("id")
        found += bool(login)
        out.execute("INSERT OR REPLACE INTO github_logins VALUES (?,?,?,?,?,?,?,?,?)",
                    (pid, cohort, method, r.status_code, login, gid if gid is not None else uid,
                     repo if method == "COMMIT_API" else None, sha if method == "COMMIT_API" else None,
                     datetime.now(timezone.utc).isoformat()))
        out.commit()

        remaining = int(r.headers.get("X-RateLimit-Remaining", "5000"))
        if i % 100 == 0 or i == len(work):
            rate = i / max(time.time() - t0, 1)
            log(f"{i}/{len(work)} looked up, {found} logins found, {remaining} API calls left this hour, "
                f"~{(len(work) - i) / rate / 60:.0f} min to go")
        if remaining <= a.reserve and i < len(work):
            reset = int(r.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset - time.time(), 0) + 1
            if not a.wait:
                log(f"only {remaining} calls left this hour; stopping. Re-run in {wait / 60:.0f} min to continue")
                return
            log(f"only {remaining} calls left; waiting {wait:.0f}s for the reset"); time.sleep(wait)
    log(f"done: {found} of {len(work)} logins found in {(time.time() - t0) / 60:.1f} min, {calls} API calls")


if __name__ == "__main__":
    main()
