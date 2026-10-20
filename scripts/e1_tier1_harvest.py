"""Enrichment step 1: Tier-1 GitHub harvest + classification for a cohort CSV.

Reads a CSV with person_id,github_login (e.g. exports/p1_cohort.csv), pulls each person's public GitHub
profile and owned repos, and classifies them into talent evidence (enrichment/tier1.py).

Per person (2 API calls):
  - gh:<id> person -> GET /user/{id}   (survives login renames); otherwise GET /users/{login}
  - then              GET /users/{login}/repos?type=owner&sort=pushed&per_page=100

Raw responses (repos slimmed to the fields the classifier reads) go to data/tier1_github.sqlite, so
classification can be re-run without the network. Resumable: people fetched within --max-age-days are
skipped. Rate limits handled as in m5_lookup_github_logins.py.

Outputs: out/enrichment/p1_tier1_enriched.json (every person) + out/enrichment/P1_TIER1_DEMO.md.

Run:  uv run scripts/e1_tier1_harvest.py --wait                 # fetch what's missing/stale, then classify
      uv run scripts/e1_tier1_harvest.py --no-fetch             # classify from the cache only
      uv run scripts/e1_tier1_harvest.py --backfill-descriptions --wait   # re-pull repos cached without descriptions
Token: GITHUB_TOKEN env var, else /root/.github_token.
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enrichment import tier1  # noqa: E402

DB = ROOT / "data" / "talent_seed.duckdb"
CACHE = ROOT / "data" / "tier1_github.sqlite"
OUT_DIR = ROOT / "out" / "enrichment"
TOKEN_FILE = Path("/root/.github_token")
REPO_FIELDS = ("name", "full_name", "html_url", "fork", "language", "topics", "description", "homepage",
               "stargazers_count", "created_at", "pushed_at")  # description, homepage: input for the AI step

SCHEMA = """
CREATE TABLE IF NOT EXISTS github_raw (
    person_id    TEXT PRIMARY KEY,
    login        TEXT,               -- current login (may differ from Talent Seed after a rename)
    api_status   INTEGER NOT NULL,   -- status of the user lookup: 200 found, 404 gone
    user_json    TEXT,
    repos_json   TEXT,               -- list of repos, REPO_FIELDS only
    fetched_at   TEXT NOT NULL
);
"""
FINAL = (200, 404)


def log(msg):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}", flush=True)


def token():
    t = os.environ.get("GITHUB_TOKEN") or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not t:
        sys.exit("No GitHub token: set GITHUB_TOKEN or write it to /root/.github_token")
    return t


def read_csv(path):
    with open(path, newline="") as f:
        return [(r["person_id"].strip(), r["github_login"].strip()) for r in csv.DictReader(f)
                if r["person_id"].strip() and r["github_login"].strip()]


def seed_rows(pids):
    con = duckdb.connect(str(DB), read_only=True)  # closed right away so a rebuild is never blocked
    try:
        cur = con.execute("""
            SELECT person_id, display_name, github_login, priority_cohort, country, commit_count,
                   repository_count, active_days_in_window, ecosystem_count, top_level_ecosystems
            FROM talent_seed WHERE list_contains(?, person_id)""", [pids])
        cols = [d[0] for d in cur.description]
        return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}
    finally:
        con.close()


class RateLimited(Exception):
    pass


def get(s, path, wait):
    """GET with retries; returns the response for any final status, raises RateLimited when told to stop."""
    for attempt in range(4):
        try:
            r = s.get("https://api.github.com" + path, timeout=30)
        except requests.RequestException as e:  # network blip: back off briefly and retry
            log(f"  network error on {path} ({e.__class__.__name__}); retry {attempt + 1}/3")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (403, 429) and ("Retry-After" in r.headers or r.headers.get("X-RateLimit-Remaining") == "0"):
            secs = int(r.headers.get("Retry-After") or max(int(r.headers.get("X-RateLimit-Reset", "0")) - time.time(), 1))
            if not wait:
                raise RateLimited(secs)
            log(f"rate limited; waiting {secs}s"); time.sleep(secs + 1)
            continue
        if r.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        return r
    return None


def session():
    s = requests.Session()
    s.headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                      "User-Agent": "talent-seed-tier1-harvest", "Authorization": f"Bearer {token()}"})
    return s


def open_cache():
    out = sqlite3.connect(CACHE)
    out.execute("PRAGMA journal_mode=WAL")
    out.executescript(SCHEMA)
    return out


def backfill_descriptions(people, reserve, wait):
    """Re-pull the repo list (1 call) for cached people whose repos were saved without `description`."""
    out = open_cache()
    pids = {p for p, _ in people}
    work = [(pid, login) for pid, login, repos_json in
            out.execute("SELECT person_id, login, repos_json FROM github_raw WHERE api_status = 200")
            if pid in pids and any("description" not in x for x in json.loads(repos_json or "[]"))]
    log(f"{len(work)} people need repo descriptions")
    s = session()
    t0 = time.time()
    for i, (pid, login) in enumerate(work, 1):
        try:
            r = get(s, f"/users/{login}/repos?type=owner&sort=pushed&per_page=100", wait)
        except RateLimited as e:
            log(f"rate limited; stopping. Re-run in {int(e.args[0]) // 60 + 1} min to continue ({i - 1}/{len(work)} done)")
            return False
        if r is None or r.status_code != 200:
            log(f"  repos failed for {pid} ({r.status_code if r is not None else 'no response'}); retry next run")
            continue
        out.execute("UPDATE github_raw SET repos_json = ? WHERE person_id = ?",
                    (json.dumps([{k: x.get(k) for k in REPO_FIELDS} for x in r.json()]), pid))
        out.commit()
        remaining = int(r.headers.get("X-RateLimit-Remaining", "5000"))
        if i % 100 == 0 or i == len(work):
            rate = i / max(time.time() - t0, 1)
            log(f"{i}/{len(work)} backfilled, {remaining} API calls left this hour, "
                f"~{(len(work) - i) / rate / 60:.0f} min to go at current pace")
        if remaining <= reserve and i < len(work):
            secs = max(int(r.headers.get("X-RateLimit-Reset", "0")) - time.time(), 0) + 1
            if not wait:
                log(f"only {remaining} calls left this hour; stopping. Re-run in {secs / 60:.0f} min to continue")
                return False
            log(f"only {remaining} calls left; waiting {secs:.0f}s for the reset"); time.sleep(secs)
    log(f"backfill done in {(time.time() - t0) / 60:.1f} min")
    return True


GQL_REPO = """name nameWithOwner url isFork description homepageUrl stargazerCount createdAt pushedAt
  primaryLanguage { name } repositoryTopics(first: 20) { nodes { topic { name } } }"""
GQL_USER = f"""databaseId login name company bio email isHireable location websiteUrl twitterUsername createdAt
  followers {{ totalCount }} socialAccounts(first: 10) {{ nodes {{ provider url displayName }} }}
  publicRepos: repositories(privacy: PUBLIC, ownerAffiliations: OWNER) {{ totalCount }}
  repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER,
               orderBy: {{field: PUSHED_AT, direction: DESC}}) {{ nodes {{ {GQL_REPO} }} }}"""


def gql_rest_shape(u):
    """GraphQL User -> (user, repos) shaped like the REST bodies the classifier and cache expect."""
    user = {"login": u["login"], "id": u["databaseId"], "name": u["name"], "company": u["company"], "bio": u["bio"],
            "email": u["email"] or None, "hireable": u["isHireable"] or None,
            "location": u["location"], "blog": u["websiteUrl"] or "",
            "twitter_username": u["twitterUsername"], "created_at": u["createdAt"],
            "followers": u["followers"]["totalCount"], "public_repos": u["publicRepos"]["totalCount"],
            "social_accounts": [{"provider": a["provider"].lower(), "url": a["url"], "display_name": a["displayName"]}
                                for a in u["socialAccounts"]["nodes"]]}  # same shape as REST /social_accounts
    repos = [{"name": r["name"], "full_name": r["nameWithOwner"], "html_url": r["url"], "fork": r["isFork"],
              "language": (r["primaryLanguage"] or {}).get("name"),
              "topics": [t["topic"]["name"] for t in r["repositoryTopics"]["nodes"]],
              "description": r["description"], "homepage": r["homepageUrl"], "stargazers_count": r["stargazerCount"],
              "created_at": r["createdAt"], "pushed_at": r["pushedAt"]} for r in u["repositories"]["nodes"]]
    return user, repos


def gql_batch(s, batch, wait):
    """One GraphQL query for a batch of (person_id, login). Returns ({pid: (user, repos) or None}, rateLimit).

    gh:<id> people are looked up by node ID (survives renames); others by login. A person missing from the
    answer (deleted account) maps to None."""
    from inspect_developer import encode_github_user_node_ids
    fields = []
    for i, (pid, login) in enumerate(batch):
        if pid.startswith("gh:"):
            fields.append(f'p{i}: node(id: "{encode_github_user_node_ids(int(pid[3:]))[1]}") {{ ... on User {{ {GQL_USER} }} }}')
        else:
            fields.append(f'p{i}: user(login: {json.dumps(login)}) {{ {GQL_USER} }}')
    query = "query { " + "\n".join(fields) + " rateLimit { cost remaining resetAt } }"
    for attempt in range(4):
        try:
            r = s.post("https://api.github.com/graphql", json={"query": query}, timeout=90)
        except requests.RequestException as e:
            log(f"  network error ({e.__class__.__name__}); retry {attempt + 1}/3")
            time.sleep(5 * (attempt + 1))
            continue
        if r.status_code in (403, 429) and ("Retry-After" in r.headers or r.headers.get("X-RateLimit-Remaining") == "0"):
            secs = int(r.headers.get("Retry-After") or max(int(r.headers.get("X-RateLimit-Reset", "0")) - time.time(), 1))
            if not wait:
                raise RateLimited(secs)
            log(f"rate limited; waiting {secs}s"); time.sleep(secs + 1)
            continue
        if r.status_code >= 500:  # usually a timeout on a heavy batch: caller splits it
            return None, None
        body = r.json()
        data = body.get("data") or {}
        bad = [e for e in body.get("errors") or [] if e.get("type") != "NOT_FOUND"]
        if bad or r.status_code != 200 or not data:
            raise RuntimeError(f"GraphQL error: {r.status_code} {(bad or body.get('errors') or body)!s:.300}")
        out = {}
        for i, (pid, _) in enumerate(batch):
            u = data.get(f"p{i}")
            out[pid] = gql_rest_shape(u) if u and u.get("login") else None
        return out, data["rateLimit"]
    return None, None


def fetch_graphql(people, max_age_days, reserve, wait, batch_size, only_cached):
    """Like fetch(), via GraphQL in batches; also re-pulls cached people saved without repo descriptions or
    social accounts (LinkedIn etc.; REST needs an extra call per person for those, GraphQL gets them free).

    only_cached: touch only people already in the cache (safe to run next to a REST fetch that is still
    adding new people, since that run never revisits people it has passed)."""
    out = open_cache()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    cached = {pid: (status, uj, rj, at) for pid, status, uj, rj, at in
              out.execute("SELECT person_id, api_status, user_json, repos_json, fetched_at FROM github_raw")}
    fresh = {pid for pid, (status, uj, rj, at) in cached.items()
             if at >= cutoff and (status == 404 or ("social_accounts" in json.loads(uj)
                                                    and all("description" in x for x in json.loads(rj or "[]"))))}
    work = [p for p in people if p[0] not in fresh and (p[0] in cached or not only_cached)]
    log(f"{len(work)} people to fetch via GraphQL ({len(people) - len(work)} skipped: complete"
        f"{' or not cached yet' if only_cached else ''})")
    s = session()
    found = gone = done = 0
    t0 = time.time()
    queue = [work[i:i + batch_size] for i in range(0, len(work), batch_size)]
    while queue:
        batch = queue.pop(0)
        try:
            res, rl = gql_batch(s, batch, wait)
        except RateLimited as e:
            log(f"rate limited; stopping. Re-run in {int(e.args[0]) // 60 + 1} min to continue ({done}/{len(work)} done)")
            return False
        if res is None:
            if len(batch) == 1:
                log(f"  giving up on {batch[0][0]} for this run")
                continue
            log(f"  batch of {len(batch)} failed (timeout?); splitting")
            queue[:0] = [batch[:len(batch) // 2], batch[len(batch) // 2:]]
            continue
        now = datetime.now(timezone.utc).isoformat()
        for pid, login in batch:
            got = res[pid]
            if got:
                user, repos = got
                found += 1
            else:
                user = repos = None
                gone += 1
            out.execute("INSERT OR REPLACE INTO github_raw VALUES (?,?,?,?,?,?)",
                        (pid, user["login"] if user else login, 200 if user else 404,
                         json.dumps(user) if user else None, json.dumps(repos) if user else None, now))
        out.commit()
        done += len(batch)
        if done % (batch_size * 10) < len(batch) or not queue:
            rate = done / max(time.time() - t0, 1)
            log(f"{done}/{len(work)} fetched ({found} found, {gone} gone), batch cost {rl['cost']}, "
                f"{rl['remaining']} points left, ~{(len(work) - done) / rate / 60:.0f} min to go at current pace")
        if rl["remaining"] <= reserve and queue:
            secs = max(datetime.fromisoformat(rl["resetAt"]).timestamp() - time.time(), 0) + 1
            if not wait:
                log(f"only {rl['remaining']} points left this hour; stopping. Re-run in {secs / 60:.0f} min to continue")
                return False
            log(f"only {rl['remaining']} points left; waiting {secs:.0f}s for the reset"); time.sleep(secs)
    log(f"GraphQL fetch done: {found} found, {gone} gone, {(time.time() - t0) / 60:.1f} min")
    return True


def fetch(people, max_age_days, reserve, wait):
    out = open_cache()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    fresh = {r[0] for r in out.execute(
        f"SELECT person_id FROM github_raw WHERE api_status IN ({','.join(map(str, FINAL))}) AND fetched_at >= ?",
        (cutoff,))}
    work = [p for p in people if p[0] not in fresh]
    log(f"{len(work)} people to fetch ({len(people) - len(work)} fetched within {max_age_days} days)")
    if not work:
        return True

    s = session()
    found = gone = 0
    t0 = time.time()
    for i, (pid, login) in enumerate(work, 1):
        path = f"/user/{pid[3:]}" if pid.startswith("gh:") else f"/users/{login}"
        try:
            r = get(s, path, wait)
            if r is None or r.status_code not in FINAL:
                log(f"  giving up on {pid} for this run ({r.status_code if r is not None else 'no response'})")
                continue
            user = repos = None
            if r.status_code == 200:
                user = r.json()
                rr = get(s, f"/users/{user['login']}/repos?type=owner&sort=pushed&per_page=100", wait)
                if rr is None or rr.status_code != 200:
                    log(f"  repos failed for {pid} ({rr.status_code if rr is not None else 'no response'}); retry next run")
                    continue
                repos = [{k: x.get(k) for k in REPO_FIELDS} for x in rr.json()]
                r = rr
                found += 1
            else:
                gone += 1
        except RateLimited as e:
            log(f"rate limited; stopping. Re-run in {int(e.args[0]) // 60 + 1} min to continue ({i - 1}/{len(work)} done)")
            return False
        out.execute("INSERT OR REPLACE INTO github_raw VALUES (?,?,?,?,?,?)",
                    (pid, user["login"] if user else login, 200 if user else 404,
                     json.dumps(user) if user else None, json.dumps(repos) if user else None,
                     datetime.now(timezone.utc).isoformat()))
        out.commit()

        remaining = int(r.headers.get("X-RateLimit-Remaining", "5000"))
        if i % 100 == 0 or i == len(work):
            rate = i / max(time.time() - t0, 1)
            log(f"{i}/{len(work)} fetched ({found} found, {gone} gone), {remaining} API calls left this hour, "
                f"~{(len(work) - i) / rate / 60:.0f} min to go at current pace")
        if remaining <= reserve and i < len(work):
            secs = max(int(r.headers.get("X-RateLimit-Reset", "0")) - time.time(), 0) + 1
            if not wait:
                log(f"only {remaining} calls left this hour; stopping. Re-run in {secs / 60:.0f} min to continue")
                return False
            log(f"only {remaining} calls left; waiting {secs:.0f}s for the reset"); time.sleep(secs)
    log(f"fetch done: {found} found, {gone} gone, {(time.time() - t0) / 60:.1f} min")
    return True


def classify(people, sample_size):
    rows = seed_rows([p for p, _ in people])
    cache = sqlite3.connect(CACHE)
    raw = {r[0]: r[1:] for r in cache.execute("SELECT person_id, api_status, user_json, repos_json, fetched_at FROM github_raw")}
    concepts = tier1.load_concepts()
    results, missing = [], 0
    for pid, _ in people:
        if pid not in raw or pid not in rows:
            missing += 1
            continue
        status, user_json, repos_json, fetched_at = raw[pid]
        user = json.loads(user_json) if status == 200 else None
        res = tier1.classify(rows[pid], user, json.loads(repos_json) if user else [], concepts)
        res["enriched_at"] = fetched_at
        results.append(res)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "p1_tier1_enriched.json").write_text(json.dumps(results, indent=1, ensure_ascii=False, default=str))

    # Demo sample: the richest half and the thinnest half, so honest UNKNOWNs show next to strong profiles.
    def n_known(r):
        return sum(e["status"] != "UNKNOWN" for e in r["evidence"])
    ranked = sorted(results, key=lambda r: (-n_known(r), r["talent"]["person_id"]))
    sample = ranked[:sample_size - sample_size // 2] + ranked[len(ranked) - sample_size // 2:]
    (OUT_DIR / "P1_TIER1_DEMO.md").write_text(tier1.demo_md(results, sample), encoding="utf-8")
    log(f"classified {len(results)} people ({missing} not fetched yet); wrote {OUT_DIR.relative_to(ROOT)}/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "exports" / "p1_cohort.csv"), help="person_id,github_login")
    ap.add_argument("--max-age-days", type=int, default=30, help="re-fetch people fetched longer ago than this")
    ap.add_argument("--reserve", type=int, default=100, help="stop/wait when this many API calls remain this hour")
    ap.add_argument("--wait", action="store_true", help="sleep until the rate limit resets instead of stopping")
    ap.add_argument("--no-fetch", action="store_true", help="classify from the cache only")
    ap.add_argument("--backfill-descriptions", action="store_true",
                    help="re-pull repo lists cached without descriptions, then classify")
    ap.add_argument("--graphql", action="store_true",
                    help="fetch via GraphQL in batches (missing, stale, or without descriptions), then classify")
    ap.add_argument("--batch-size", type=int, default=5, help="people per GraphQL query (10 times out)")
    ap.add_argument("--only-cached", action="store_true", help="with --graphql: only people already in the cache")
    ap.add_argument("--sample", type=int, default=10, help="people shown in full in the demo markdown")
    a = ap.parse_args()

    people = read_csv(a.csv)
    log(f"{len(people)} people in {a.csv}")
    if a.graphql:
        fetch_graphql(people, a.max_age_days, a.reserve, a.wait, a.batch_size, a.only_cached)
    elif a.backfill_descriptions:
        backfill_descriptions(people, a.reserve, a.wait)
    elif not a.no_fetch:
        fetch(people, a.max_age_days, a.reserve, a.wait)
    classify(people, a.sample)


if __name__ == "__main__":
    main()
