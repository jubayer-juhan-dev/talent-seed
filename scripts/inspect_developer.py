"""Milestone 3: inspect one developer end to end from Open Dev Data (+ GitHub for account resolution).

Usage:
    uv run scripts/inspect_developer.py <github_username | email> [...more] [--out-dir out/inspect] [--no-github]

Several inputs can be passed at once; the large ODD tables (not clustered by developer) are then
scanned once for the whole batch. Every match is reported - when an input maps to more than one
canonical developer, all of them are returned and none is picked.

Rules honoured here:
- Reads data/odd.duckdb read-only; raw Parquet is never touched.
- Emails are contact points with email_status = 'UNVERIFIED'; no employer is inferred from domains.
- GITHUB_TOKEN comes from the environment only; responses are cached on disk; rate limits respected.
- Thresholds live in config/talent_seed_thresholds.toml.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import tomllib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "odd.duckdb"
CONFIG = ROOT / "config" / "talent_seed_thresholds.toml"
GH_CACHE = ROOT / "data" / "cache" / "github"
ATTRIBUTION = "Data from Electric Capital Open Dev Data (https://opendevdata.org), licensed CC BY 4.0."
NOREPLY_RE = re.compile(r"^(?:(\d+)\+)?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\[bot\])?)@users\.noreply\.github\.com$")


# --------------------------------------------------------------------------- GitHub node IDs

def decode_github_node_id(node_id: str | None) -> tuple[str | None, int | None]:
    """Return (kind, numeric database id) for a GitHub GraphQL node ID, or (None, None)."""
    if not node_id:
        return None, None
    if node_id.startswith(("MDQ6", "MDM6")):  # legacy: base64("04:User123") / base64("03:Bot123")
        try:
            text = base64.b64decode(node_id + "=" * (-len(node_id) % 4)).decode()
            m = re.fullmatch(r"\d+:(User|Bot)(\d+)", text)
            return (m.group(1), int(m.group(2))) if m else (None, None)
        except Exception:
            return None, None
    m = re.fullmatch(r"(U|BOT)_(.+)", node_id)  # new: prefix + base64url(msgpack [0, id])
    if not m:
        return None, None
    try:
        raw = base64.urlsafe_b64decode(m.group(2) + "=" * (-len(m.group(2)) % 4))
    except Exception:
        return None, None
    if len(raw) < 3 or raw[0] != 0x92 or raw[1] != 0x00:
        return None, None
    tag, body = raw[2], raw[3:]
    if tag < 0x80:
        num = tag
    elif tag in (0xCC, 0xCD, 0xCE, 0xCF):
        width = {0xCC: 1, 0xCD: 2, 0xCE: 4, 0xCF: 8}[tag]
        num = int.from_bytes(body[:width], "big")
    else:
        return None, None
    return ("User" if m.group(1) == "U" else "Bot"), num


def encode_github_user_node_ids(user_id: int) -> list[str]:
    """Both node-ID encodings of a GitHub user id (legacy and new), for matching ODD."""
    legacy = base64.b64encode(f"04:User{user_id}".encode()).decode()
    if user_id < 0x80:
        packed = bytes([0x92, 0x00, user_id])
    elif user_id < 1 << 8:
        packed = bytes([0x92, 0x00, 0xCC]) + user_id.to_bytes(1, "big")
    elif user_id < 1 << 16:
        packed = bytes([0x92, 0x00, 0xCD]) + user_id.to_bytes(2, "big")
    elif user_id < 1 << 32:
        packed = bytes([0x92, 0x00, 0xCE]) + user_id.to_bytes(4, "big")
    else:
        packed = bytes([0x92, 0x00, 0xCF]) + user_id.to_bytes(8, "big")
    new = "U_" + base64.urlsafe_b64encode(packed).decode().rstrip("=")
    return [legacy, new]


# --------------------------------------------------------------------------- GitHub REST client

class GitHub:
    def __init__(self, cfg: dict, enabled: bool):
        self.cfg = cfg
        self.enabled = enabled
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/vnd.github+json",
                                     "X-GitHub-Api-Version": "2022-11-28",
                                     "User-Agent": "talent-seed-inspector"})
        token = os.environ.get("GITHUB_TOKEN")
        self.authenticated = bool(token)
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.calls = 0
        GH_CACHE.mkdir(parents=True, exist_ok=True)

    def get(self, path: str) -> tuple[int, dict | None]:
        """GET with on-disk cache (200/404/422 only) and rate-limit handling."""
        key = re.sub(r"[^A-Za-z0-9_.-]", "_", path.strip("/"))
        cache = GH_CACHE / f"{key}.json"
        if cache.exists():
            c = json.loads(cache.read_text())
            return c["status"], c["body"]
        if not self.enabled:
            return 0, None
        for _ in range(3):
            r = self.session.get(f"https://api.github.com{path}", timeout=30)
            self.calls += 1
            remaining = int(r.headers.get("X-RateLimit-Remaining", "1"))
            reset = int(r.headers.get("X-RateLimit-Reset", "0"))
            if r.status_code in (403, 429) and (remaining == 0 or "Retry-After" in r.headers):
                wait = int(r.headers.get("Retry-After", max(reset - time.time(), 1)))
                if wait > self.cfg["max_sleep_seconds"]:
                    raise RuntimeError(f"GitHub rate limit exhausted; resets in {wait}s (set GITHUB_TOKEN)")
                print(f"  rate limited; sleeping {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else None
            if r.status_code in (200, 404, 422):
                cache.write_text(json.dumps({"status": r.status_code, "body": body,
                                             "fetched_at": datetime.now(timezone.utc).isoformat()}))
            if remaining <= self.cfg["min_remaining_before_sleep"]:
                wait = max(reset - time.time(), 0) + 1
                if wait <= self.cfg["max_sleep_seconds"]:
                    print(f"  rate limit nearly exhausted; sleeping {wait:.0f}s", file=sys.stderr)
                    time.sleep(wait)
            return r.status_code, body
        raise RuntimeError(f"GitHub request kept failing: {path}")


# --------------------------------------------------------------------------- helpers

def rows(con, sql: str, params=None) -> list[dict]:
    rel = con.execute(sql, params or [])
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def iso(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return iso(o)


def placeholders(n: int) -> str:
    return ",".join(["?"] * n)


# --------------------------------------------------------------------------- core

class Inspector:
    def __init__(self, cfg: dict, use_github: bool):
        self.cfg = cfg
        self.con = duckdb.connect(str(DB), read_only=True)
        self.con.execute("SET TimeZone='UTC'; SET memory_limit='4GB'; SET threads=4;")
        lin = rows(self.con, "SELECT * FROM _odd_lineage WHERE table_name='commits'")[0]
        self.snapshot_id = lin["source_snapshot_id"]
        self.snapshot_date = lin["source_snapshot_date"]
        raw_dir = Path(lin["source_file"]).parent
        # as-of = last day with activity data (from Parquet footer stats; no scan)
        self.as_of = date.fromisoformat(self.con.execute(
            f"SELECT max(stats_max_value) FROM parquet_metadata('{raw_dir}/developer_activities.parquet') "
            "WHERE path_in_schema='day'").fetchone()[0])
        self.window_start = self.as_of - timedelta(days=cfg["activity"]["window_days"] - 1)
        self.gh = GitHub(cfg["github"], use_github)
        self.tables_used: set[str] = {"_odd_lineage", "developer_activities"}
        # root chains: is_chain=1 and no is_chain=1 ancestor
        self.con.execute("""CREATE TEMP TABLE root_chains AS
            SELECT e.id, e.name FROM ecosystems e WHERE e.is_chain = 1 AND NOT EXISTS (
              SELECT 1 FROM ecosystems_child_ecosystems_recursive r JOIN ecosystems p ON p.id = r.parent_id
              WHERE r.child_id = e.id AND p.is_chain = 1)""")
        self.tables_used |= {"ecosystems", "ecosystems_child_ecosystems_recursive"}

    # ---- step 1: input -> canonical developer ids
    def match(self, raw: str) -> list[dict]:
        q = raw.strip()
        matches: dict[int, set[str]] = {}
        self.tables_used.add("dev_identity_variants")
        if "@" in q:
            for r in rows(self.con, "SELECT DISTINCT canonical_developer_id id FROM dev_identity_variants "
                                    "WHERE email_norm = ?", [q.lower()]):
                matches.setdefault(r["id"], set()).add("COMMIT_AUTHOR_EMAIL")
        else:
            login = q.lower().lstrip("@")
            pat = r"(\d+\+)?" + re.escape(login) + r"@users\.noreply\.github\.com"
            for r in rows(self.con, "SELECT DISTINCT canonical_developer_id id FROM dev_identity_variants "
                                    "WHERE email_norm LIKE ? AND regexp_full_match(email_norm, ?)",
                          [f"%{login}@users.noreply.github.com", pat]):
                matches.setdefault(r["id"], set()).add("COMMIT_AUTHOR_NOREPLY_EMAIL")
            status, user = self.gh.get(f"/users/{login}")
            if status == 200 and user:
                ids = encode_github_user_node_ids(user["id"]) + ([user["node_id"]] if user.get("node_id") else [])
                self.tables_used.add("canonical_developers")
                for r in rows(self.con, f"SELECT id FROM canonical_developers WHERE primary_github_user_id IN "
                                        f"({placeholders(len(ids))})", ids):
                    matches.setdefault(r["id"], set()).add("ODD_GITHUB_ID")
        return [{"canonical_developer_id": k, "match_methods": sorted(v)} for k, v in sorted(matches.items())]

    # ---- steps 2-5: batch facts for a set of developers
    def facts(self, dev_ids: list[int]) -> dict:
        ph = placeholders(len(dev_ids))
        cfg = self.cfg
        f = {}
        f["devs"] = {r["id"]: r for r in rows(self.con, f"SELECT * FROM canonical_developers WHERE id IN ({ph})", dev_ids)}
        f["locations"] = {r["canonical_developer_id"]: r for r in rows(self.con,
            f"""SELECT canonical_developer_id, input, country, admin_level_1, locality, formatted_address, created_at
                FROM canonical_developer_locations WHERE canonical_developer_id IN ({ph})""", dev_ids)}
        f["variants"] = rows(self.con, f"""
            SELECT v.*, (SELECT count(DISTINCT canonical_developer_id) FROM dev_identity_variants w
                         WHERE w.email_norm = v.email_norm) AS devs_sharing_email
            FROM dev_identity_variants v WHERE canonical_developer_id IN ({ph})""", dev_ids)
        f["repos"] = rows(self.con, f"""
            SELECT a.canonical_developer_id, a.repo_id, r.name AS repo_name, r.link AS repo_url,
                   r.is_blacklist, r.num_stars, r.repo_created_at, sum(a.num_commits)::BIGINT AS commits,
                   coalesce(sum(a.num_commits) FILTER (WHERE a.day < r.repo_created_at::DATE), 0)::BIGINT
                       AS commits_before_repo_created,
                   count(DISTINCT a.day) AS active_days, min(a.day) AS first_active_date, max(a.day) AS last_active_date
            FROM developer_activities a LEFT JOIN repos r ON r.id = a.repo_id
            WHERE a.canonical_developer_id IN ({ph}) GROUP BY ALL""", dev_ids)
        f["days"] = rows(self.con, f"""
            SELECT canonical_developer_id, day FROM developer_activities
            WHERE canonical_developer_id IN ({ph}) AND day BETWEEN ? AND ? GROUP BY ALL""",
            dev_ids + [self.window_start, self.as_of])
        # Fallback for developers absent from developer_activities although they have commits
        # (config [activity_fallback]): rebuild repo and day activity from the commits table.
        f["activity_gap_devs"] = set()
        in_da = {r["canonical_developer_id"] for r in f["repos"]}
        gap = sorted({v["canonical_developer_id"] for v in f["variants"] if v["n_commits"]} - in_da)
        if gap and cfg["activity_fallback"]["enabled"]:
            t0 = time.time()
            gph = placeholders(len(gap))
            per_day = rows(self.con, f"""
                SELECT c.canonical_developer_id, c.repo_id, c.authored_at::DATE AS day, count(*) AS n
                FROM commits c
                WHERE c.canonical_developer_id IN ({gph})
                  AND c.authored_at BETWEEN TIMESTAMPTZ '{cfg['tenure']['min_valid_commit_date']}'
                                        AND ?::DATE + INTERVAL 1 DAY
                GROUP BY ALL""", gap + [self.as_of])
            meta = {r["id"]: r for r in rows(self.con, f"""
                SELECT id, name, link, is_blacklist, num_stars, repo_created_at FROM repos
                WHERE id IN ({placeholders(len({p['repo_id'] for p in per_day}) or 1)})""",
                sorted({p["repo_id"] for p in per_day}) or [-1])}
            agg: dict[tuple, dict] = {}
            for p in per_day:
                m = meta.get(p["repo_id"], {})
                a = agg.setdefault((p["canonical_developer_id"], p["repo_id"]), {
                    "canonical_developer_id": p["canonical_developer_id"], "repo_id": p["repo_id"],
                    "repo_name": m.get("name"), "repo_url": m.get("link"), "is_blacklist": m.get("is_blacklist"),
                    "num_stars": m.get("num_stars"), "repo_created_at": m.get("repo_created_at"), "commits": 0,
                    "commits_before_repo_created": 0, "days": set()})
                a["commits"] += p["n"]
                a["days"].add(p["day"])
                if m.get("repo_created_at") and p["day"] < m["repo_created_at"].date():
                    a["commits_before_repo_created"] += p["n"]
                if self.window_start <= p["day"] <= self.as_of:
                    f["days"].append({"canonical_developer_id": p["canonical_developer_id"], "day": p["day"]})
            for a in agg.values():
                ds = a.pop("days")
                f["repos"].append({**a, "active_days": len(ds), "first_active_date": min(ds), "last_active_date": max(ds)})
            f["days"] = [dict(t) for t in {tuple(sorted(d.items())) for d in f["days"]}]
            f["activity_gap_devs"] = set(gap)
            self.tables_used.add("commits")
            print(f"  activity fallback from commits for {len(gap)} dev(s): {time.time() - t0:.0f}s", file=sys.stderr)

        repo_ids = sorted({r["repo_id"] for r in f["repos"]}) or [-1]
        rph = placeholders(len(repo_ids))
        f["repo_ecos"] = rows(self.con, f"""
            SELECT er.repo_id, e.id AS ecosystem_id, e.name AS ecosystem_name, e.is_chain, e.is_category,
                   e.is_virtual, (rc.id IS NOT NULL) AS is_root_chain
            FROM ecosystems_repos er JOIN ecosystems e ON e.id = er.ecosystem_id
            LEFT JOIN root_chains rc ON rc.id = e.id WHERE er.repo_id IN ({rph})""", repo_ids)
        eco_ids = sorted({r["ecosystem_id"] for r in f["repo_ecos"]}) or [-1]
        eph = placeholders(len(eco_ids))
        f["eco_roots"] = rows(self.con, f"""
            SELECT DISTINCT e.id AS ecosystem_id, rc.id AS root_id, rc.name AS root_name
            FROM ecosystems e JOIN root_chains rc ON rc.id = e.id WHERE e.id IN ({eph})
            UNION
            SELECT DISTINCT r.child_id, rc.id, rc.name FROM ecosystems_child_ecosystems_recursive r
            JOIN root_chains rc ON rc.id = r.parent_id WHERE r.child_id IN ({eph})""", eco_ids + eco_ids)
        f["repo_eco_counts"] = {r["repo_id"]: r["n"] for r in rows(self.con, f"""
            SELECT repo_id, count(*) n FROM ecosystems_repos WHERE repo_id IN ({rph}) GROUP BY 1""", repo_ids)}
        self.tables_used |= {"canonical_developers", "canonical_developer_locations", "repos", "ecosystems_repos"}

        # ODD per-developer, per-ecosystem fields (full scans of large files, once per batch)
        t0 = time.time()
        f["odd_exclusive"] = rows(self.con, f"""
            SELECT canonical_developer_id, ecosystem_id, day, is_exclusive FROM eco_developer_activities
            WHERE canonical_developer_id IN ({ph}) AND day BETWEEN ? AND ?
              AND ecosystem_id IN (SELECT id FROM root_chains)""", dev_ids + [self.window_start, self.as_of])
        f["odd_rank"] = rows(self.con, f"""
            SELECT canonical_developer_id, ecosystem_id, max(day) AS row_date, arg_max(contribution_rank, day) AS contribution_rank,
                   arg_max(points, day) AS points FROM eco_developer_contribution_ranks
            WHERE canonical_developer_id IN ({ph}) AND day <= ? AND ecosystem_id IN (SELECT id FROM root_chains)
            GROUP BY ALL""",
            dev_ids + [self.as_of])
        f["odd_tenure"] = rows(self.con, f"""
            SELECT canonical_developer_id, ecosystem_id, max(day) AS row_date, arg_max(tenure_days, day) AS tenure_days,
                   arg_max(category, day) AS category FROM eco_developer_tenures
            WHERE canonical_developer_id IN ({ph}) AND day <= ? AND ecosystem_id IN (SELECT id FROM root_chains)
            GROUP BY ALL""",
            dev_ids + [self.as_of])
        print(f"  ODD per-ecosystem scans: {time.time() - t0:.0f}s", file=sys.stderr)
        self.tables_used |= {"eco_developer_activities", "eco_developer_contribution_ranks", "eco_developer_tenures"}
        return f

    # ---- step 6: GitHub account
    def resolve_github(self, dev: dict | None, variants: list[dict], repo_names: dict[int, str]) -> dict:
        res = {"login": None, "user_id": None, "node_id": None, "resolution_method": "UNRESOLVED",
               "resolution_commit_sha": None, "resolution_repo": None, "evidence": [], "conflicts": []}
        ev = res["evidence"]

        # (a) noreply emails, most recent first
        for v in sorted(variants, key=lambda v: v["last_seen_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            m = NOREPLY_RE.match(v["email_norm"])
            if m:
                ev.append({"method": "NOREPLY", "email": v["commit_author_email"],
                           "user_id": int(m.group(1)) if m.group(1) else None, "login": m.group(2),
                           "last_seen_at": v["last_seen_at"]})
        # (b) ODD's primary_github_user_id (GraphQL node id) -> numeric id -> current login
        odd_node = dev.get("primary_github_user_id") if dev else None
        kind, odd_uid = decode_github_node_id(odd_node)
        if odd_uid is not None:
            e = {"method": "ODD_GITHUB_ID", "node_id": odd_node, "kind": kind, "user_id": odd_uid, "login": None}
            status, body = self.gh.get(f"/user/{odd_uid}")
            e["api_status"] = status
            if status == 200 and body:
                e["login"] = body.get("login")
            ev.append(e)

        noreply = [e for e in ev if e["method"] == "NOREPLY"]
        odd = next((e for e in ev if e["method"] == "ODD_GITHUB_ID"), None)
        if noreply:
            best = next((e for e in noreply if e["user_id"]), noreply[0])
            res.update(login=best["login"], user_id=best["user_id"], resolution_method="NOREPLY")
        elif odd and odd["login"]:
            res.update(login=odd["login"], user_id=odd["user_id"], node_id=odd["node_id"],
                       resolution_method="ODD_GITHUB_ID")
        else:
            # (c) commit API on up to N commits, preferring non-bot variants with the most commits
            cands = sorted((v for v in variants if v["latest_sha1"] and v["n_bot_commits"] < v["n_commits"]),
                           key=lambda v: -v["n_commits"])
            for v in cands[: self.cfg["github"]["max_commit_api_calls"]]:
                repo = repo_names.get(v["latest_sha1_repo_id"])
                if not repo:
                    continue
                status, body = self.gh.get(f"/repos/{repo}/commits/{v['latest_sha1']}")
                author = (body or {}).get("author") if status == 200 else None
                ev.append({"method": "COMMIT_API", "repo": repo, "sha": v["latest_sha1"], "api_status": status,
                           "login": author.get("login") if author else None,
                           "user_id": author.get("id") if author else None})
                if author and author.get("login"):
                    res.update(login=author["login"], user_id=author["id"], node_id=author.get("node_id"),
                               resolution_method="COMMIT_API", resolution_commit_sha=v["latest_sha1"],
                               resolution_repo=repo)
                    break
            if res["resolution_method"] == "UNRESOLVED" and cands:
                res["resolution_commit_sha"] = cands[0]["latest_sha1"]
                res["resolution_repo"] = repo_names.get(cands[0]["latest_sha1_repo_id"])

        # fill id / current login from ODD when the chosen method agrees, and record disagreements
        if odd:
            if res["user_id"] is None and res["resolution_method"] == "NOREPLY" and odd["login"] \
                    and odd["login"].lower() == (res["login"] or "").lower():
                res["user_id"] = odd["user_id"]
            if res["user_id"] is not None and res["user_id"] != odd["user_id"]:
                res["conflicts"].append(f"resolved user_id {res['user_id']} != ODD primary_github_user_id "
                                        f"{odd['user_id']} (canonical identity may merge two GitHub accounts)")
            elif odd["login"] and res["login"] and odd["login"].lower() != res["login"].lower():
                res["conflicts"].append(f"login from {res['resolution_method']} '{res['login']}' differs from "
                                        f"current login for ODD id '{odd['login']}' (renamed account?)")
            res["node_id"] = res["node_id"] or (odd["node_id"] if res["user_id"] == odd["user_id"] else None)
        ids = {e["user_id"] for e in noreply if e["user_id"]}
        if len(ids) > 1:
            res["conflicts"].append(f"noreply emails carry {len(ids)} different GitHub user ids: {sorted(ids)}")

        # confidence (config [github_confidence])
        method = res["resolution_method"]
        corroborated = odd is not None and res["user_id"] is not None and res["user_id"] == odd["user_id"]
        if method == "UNRESOLVED":
            conf = "NONE"
        elif method == "ODD_GITHUB_ID" or (method == "NOREPLY" and corroborated):
            conf = "HIGH"
        elif method == "COMMIT_API" or (method == "NOREPLY" and res["user_id"] is not None):
            conf = "MEDIUM"
        else:
            conf = "LOW"
        if res["conflicts"] and conf != "NONE":
            conf = self.cfg["github_confidence"]["conflict_downgrades_to"]
        res["confidence"] = conf
        res["corroborated_by_odd_github_id"] = corroborated
        return res

    # ---- priority cohort (config [priority_cohort], first matching rule wins)
    def cohort(self, activity: str, tenure: str, flags: list[str]) -> dict:
        pc = self.cfg["priority_cohort"]
        for i, rule in enumerate(pc["rules"], 1):
            if "activity_segment" in rule and activity not in rule["activity_segment"]:
                continue
            if "tenure_segment" in rule and tenure not in rule["tenure_segment"]:
                continue
            if "flags_any" in rule and not any(fl.startswith(p) for fl in flags for p in rule["flags_any"]):
                continue
            return {"cohort": rule["cohort"], "rule_number": i, "reason": rule["reason"], "status": pc["status"]}
        return {"cohort": pc["default_cohort"], "rule_number": None, "reason": "no rule matched", "status": pc["status"]}

    # ---- step 5 + 7: assemble one record
    def build_record(self, inp: str, match: dict, f: dict) -> dict:
        cfg, dev_id = self.cfg, match["canonical_developer_id"]
        dev = f["devs"].get(dev_id)
        variants = [v for v in f["variants"] if v["canonical_developer_id"] == dev_id]
        repos = sorted((r for r in f["repos"] if r["canonical_developer_id"] == dev_id),
                       key=lambda r: (-r["commits"], r["repo_name"] or ""))
        repo_ids = {r["repo_id"] for r in repos}
        days = sorted(r["day"] for r in f["days"] if r["canonical_developer_id"] == dev_id)
        flags = []

        # identity variants
        placeholder_min = cfg["identity"]["placeholder_email_min_devs"]
        contact_points, names = [], {}
        by_email: dict[str, list[dict]] = {}
        for v in variants:
            by_email.setdefault(v["email_norm"], []).append(v)
            n = names.setdefault(v["commit_author_name"], {"name": v["commit_author_name"], "first_seen_at": None,
                                                           "last_seen_at": None, "n_commits": 0})
            n["n_commits"] += v["n_commits"]
            for k, fn in (("first_seen_at", min), ("last_seen_at", max)):
                vals = [x for x in (n[k], v[k]) if x is not None]
                n[k] = fn(vals) if vals else None
        for email, vs in sorted(by_email.items()):
            firsts = [v["first_seen_at"] for v in vs if v["first_seen_at"]]
            lasts = [v["last_seen_at"] for v in vs if v["last_seen_at"]]
            shared = max(v["devs_sharing_email"] for v in vs)
            cp = {"type": "EMAIL", "value": vs[0]["commit_author_email"], "value_normalized": email,
                  "email_status": "UNVERIFIED", "is_github_noreply": bool(NOREPLY_RE.match(email)),
                  "is_empty": email == "", "shared_by_n_developers": shared,
                  "is_placeholder": email == "" or shared >= placeholder_min,
                  "author_names": sorted({v["commit_author_name"] for v in vs}),
                  "first_seen_at": min(firsts) if firsts else None, "last_seen_at": max(lasts) if lasts else None,
                  "n_commits": sum(v["n_commits"] for v in vs), "source_table": "commits"}
            contact_points.append(cp)
            if cp["is_placeholder"]:
                flags.append(f"PLACEHOLDER_EMAIL: '{cp['value']}' shared by {shared} canonical developers")
        n_commits = sum(v["n_commits"] for v in variants)
        n_bot = sum(v["n_bot_commits"] for v in variants)
        n_bad = sum(v["n_commits_bad_date"] for v in variants)
        kind, _ = decode_github_node_id(dev.get("primary_github_user_id") if dev else None)
        if kind == "Bot" or (n_commits and n_bot / n_commits >= cfg["identity"]["bot_commit_share_flag"]):
            flags.append(f"PROBABLE_BOT: {n_bot}/{n_commits} commits flagged is_bot; ODD GitHub id kind={kind}")
        agent_res = [re.compile("^" + ".*".join(re.escape(x) for x in p.split("%")) + "$")
                     for p in cfg["identity"]["ai_agent_email_patterns"]]
        n_agent = sum(v["n_commits"] for v in variants if any(r.match(v["email_norm"]) for r in agent_res))
        if n_commits and n_agent / n_commits >= cfg["identity"]["ai_agent_commit_share"]:
            flags.append(f"PROBABLE_BOT: AI coding agent - {n_agent}/{n_commits} commits from AI-agent author emails")
        if dev_id in f.get("activity_gap_devs", ()):
            flags.append("ACTIVITY_TABLE_GAP: developer has commits but no developer_activities rows; repos and "
                         "active days rebuilt from the commits table (authored_at date, UTC)")
        if len(by_email) > 1 or len(names) > 1:
            flags.append(f"MERGED_IDENTITY: {len(by_email)} emails and {len(names)} author names under one canonical id")
        if n_bad:
            flags.append(f"BAD_COMMIT_DATES: {n_bad} commits with author dates outside 2005-04-01..snapshot (ignored)")
        if dev is None:
            flags.append("MISSING_CANONICAL_DEVELOPER: id appears in commits but not in canonical_developers")

        # ecosystems: drop category / virtual tags (internal lists such as "[Candidates] All Crypto")
        all_tags = [r for r in f["repo_ecos"] if r["repo_id"] in repo_ids]
        repo_ecos = [r for r in all_tags if not r["is_category"] and not r["is_virtual"]]
        dropped_tags = Counter(r["repo_id"] for r in all_tags if r["is_category"] or r["is_virtual"])
        roots_of: dict[int, list[dict]] = {}
        for r in f["eco_roots"]:
            roots_of.setdefault(r["ecosystem_id"], []).append(r)
        repo_by_id = {r["repo_id"]: r for r in repos}
        for r in repos:
            ecos = [e for e in repo_ecos if e["repo_id"] == r["repo_id"]]
            r["sub_ecosystems"] = sorted({e["ecosystem_name"] for e in ecos if not e["is_chain"]})
            r["top_level_ecosystems"] = sorted({x["root_name"] for e in ecos for x in roots_of.get(e["ecosystem_id"], [])})
            r["n_ecosystems_tagged"] = f["repo_eco_counts"].get(r["repo_id"], 0)
            r["n_category_tags_dropped"] = dropped_tags.get(r["repo_id"], 0)
            if r["n_ecosystems_tagged"] > cfg["ecosystems"]["many_ecosystems_flag"]:
                flags.append(f"REPO_MANY_ECOSYSTEMS: {r['repo_name']} is tagged to {r['n_ecosystems_tagged']} ecosystems")
            r["inherited_history"] = (r["commits"] > 0 and r["commits_before_repo_created"] / r["commits"]
                                      >= cfg["repos"]["inherited_history_share"])
            if r["is_blacklist"]:
                flags.append(f"BLACKLISTED_REPO: {r['repo_name']}")
        eco_rel: dict[tuple, dict] = {}
        for e in repo_ecos:
            rr = repo_by_id[e["repo_id"]]
            targets = [] if e["is_chain"] else [("SUB_ECOSYSTEM", e["ecosystem_id"], e["ecosystem_name"])]
            targets +=[("TOP_LEVEL", x["root_id"], x["root_name"]) for x in roots_of.get(e["ecosystem_id"], [])]
            for level, eid, name in targets:
                rel = eco_rel.setdefault((level, eid), {"level": level, "ecosystem_id": eid, "ecosystem_name": name,
                                                        "repo_ids": set(), "commits": 0, "last_active_date": None})
                if rr["repo_id"] not in rel["repo_ids"]:
                    rel["repo_ids"].add(rr["repo_id"])
                    rel["commits"] += rr["commits"]
                    rel["last_active_date"] = max(filter(None, [rel["last_active_date"], rr["last_active_date"]]))
        eco_list = sorted(({**v, "repo_count": len(v["repo_ids"]), "repo_ids": sorted(v["repo_ids"])}
                           for v in eco_rel.values()), key=lambda x: (x["level"] != "TOP_LEVEL", -x["commits"]))
        top_level = [e for e in eco_list if e["level"] == "TOP_LEVEL"]
        inherited = [r for r in repos if r["inherited_history"]]
        if inherited:
            flags.append(f"INHERITED_HISTORY: {len(inherited)} repos are mostly commits authored before the repo was "
                         f"created (forks/imports), {sum(r['commits_before_repo_created'] for r in repos)} commits in all; "
                         f"e.g. {', '.join(r['repo_name'] for r in inherited[:3])}")
        untagged = [r["repo_name"] for r in repos if not r["sub_ecosystems"] and not r["top_level_ecosystems"]]
        if untagged:
            flags.append(f"REPOS_WITHOUT_ECOSYSTEM: {len(untagged)} repos have no direct ecosystem tag")

        # metrics
        firsts = [v["first_seen_at"] for v in variants if v["first_seen_at"]]
        first_commit = min(firsts).date() if firsts else None
        last_activity = max((r["last_active_date"] for r in repos), default=None)
        if last_activity is None:
            lasts = [v["last_seen_at"] for v in variants if v["last_seen_at"]]
            last_activity = max(lasts).date() if lasts else None

        t = cfg["tenure"]
        tenure_days = (self.as_of - first_commit).days if first_commit else None
        tenure = ("UNKNOWN" if tenure_days is None else "NEWCOMER" if tenure_days <= t["newcomer_max_days"]
                  else "EMERGING" if tenure_days <= t["emerging_max_days"] else "ESTABLISHED")

        a = cfg["activity"]
        max_28 = 0
        for i, d in enumerate(days):  # sliding 28-day window over active days inside the 84-day window
            j = i
            while j < len(days) and (days[j] - d).days < a["full_time_subwindow_days"]:
                j += 1
            max_28 = max(max_28, j - i)
        activity = ("UNKNOWN" if not days else "FULL_TIME" if max_28 >= a["full_time_min_days_in_28d"]
                    else "PART_TIME" if len(days) >= a["part_time_min_active_days"] else "ONE_TIME")

        root_names = {r["id"]: r["name"] for r in rows(self.con, "SELECT id, name FROM root_chains")}
        ex = [r for r in f["odd_exclusive"] if r["canonical_developer_id"] == dev_id]
        if not ex:
            excl = "UNKNOWN"
        elif all(r["is_exclusive"] for r in ex):
            excl = "EXCLUSIVE"
        else:
            excl = "MULTICHAIN"
        window_top = sorted({e["ecosystem_name"] for e in top_level
                             if e["last_active_date"] and e["last_active_date"] >= self.window_start})
        ranks = [{"ecosystem": root_names.get(r["ecosystem_id"]), "contribution_rank": r["contribution_rank"],
                  "points": r["points"], "row_date": r["row_date"], "is_current": r["row_date"] == self.as_of} for r in f["odd_rank"] if r["canonical_developer_id"] == dev_id]
        tenures = [{"ecosystem": root_names.get(r["ecosystem_id"]), "tenure_days": r["tenure_days"],
                    "category": r["category"], "row_date": r["row_date"], "is_current": r["row_date"] == self.as_of} for r in f["odd_tenure"] if r["canonical_developer_id"] == dev_id]

        repo_names = {r["repo_id"]: r["repo_name"] for r in repos}
        missing = {v["latest_sha1_repo_id"] for v in variants} - set(repo_names)
        if missing:
            for r in rows(self.con, f"SELECT id, name FROM repos WHERE id IN ({placeholders(len(missing))})", list(missing)):
                repo_names[r["id"]] = r["name"]
        github = self.resolve_github(dev, variants, repo_names)
        for c in github["conflicts"]:
            flags.append(f"GITHUB_CONFLICT: {c}")

        cohort = self.cohort(activity, tenure, flags)
        own_repo_ids = {r["repo_id"] for r in repos if not r["inherited_history"]}
        top_level_own = {e["ecosystem_name"] for e in top_level if set(e["repo_ids"]) & own_repo_ids}
        name_counts = Counter({n["name"]: n["n_commits"] for n in names.values()})
        loc = f["locations"].get(dev_id)
        return {
            "record_type": "talent_seed",
            "schema_version": "draft-0.1 (option B: no client spec; see docs/talent_seed_record_draft.md)",
            "input": inp,
            "canonical_developer_id": dev_id,
            "match_methods": match["match_methods"],
            "display_name": name_counts.most_common(1)[0][0] if name_counts else None,
            "github": github,
            "contact_points": contact_points,
            "name_variants": sorted(names.values(), key=lambda n: -n["n_commits"]),
            "location": None if not loc else {k: loc[k] for k in
                                              ("input", "country", "admin_level_1", "locality", "formatted_address")}
                         | {"source_table": "canonical_developer_locations", "geocoded_at": loc["created_at"]},
            "first_commit_date": first_commit,
            "last_activity_date": last_activity,
            "repository_count": len(repos),
            "ecosystem_count": len(top_level),
            "ecosystem_count_excluding_inherited": len(top_level_own),
            "sub_ecosystem_count": sum(1 for e in eco_list if e["level"] == "SUB_ECOSYSTEM"),
            "commit_count": n_commits,
            "commit_count_bot": n_bot,
            "commit_count_in_repo_activity": sum(r["commits"] for r in repos),
            "commit_count_excluding_inherited": sum(r["commits"] - r["commits_before_repo_created"] for r in repos),
            "repository_count_excluding_inherited": sum(1 for r in repos if not r["inherited_history"]),
            "tenure_segment": tenure,
            "tenure_days": tenure_days,
            "activity_segment": activity,
            "activity_segment_reason": None if days else (
                "NO_ACTIVITY_IN_WINDOW" if last_activity else "NO_ACTIVITY_DATA"),
            "active_days_in_window": len(days),
            "max_active_days_in_28d": max_28,
            "exclusivity": {"status": excl, "method": "ODD eco_developer_activities.is_exclusive (root chains)",
                            "active_eco_days_in_window": len(ex),
                            "exclusive_eco_days_in_window": sum(1 for r in ex if r["is_exclusive"]),
                            "top_level_ecosystems_in_window": window_top,
                            "distinct_top_level_ecosystems_in_window": len(window_top)},
            "odd_contribution_rank_latest": ranks,  # ODD only has rows while the dev is a 28d MAD
            "odd_tenure_latest": tenures,
            "priority_cohort": cohort["cohort"],
            "priority_cohort_detail": cohort,
            "data_quality_flags": flags,
            "repos": [{k: r[k] for k in ("repo_id", "repo_name", "repo_url", "commits", "active_days",
                                         "first_active_date", "last_active_date", "repo_created_at",
                                         "commits_before_repo_created", "inherited_history", "top_level_ecosystems",
                                         "sub_ecosystems", "n_ecosystems_tagged", "n_category_tags_dropped",
                                         "num_stars", "is_blacklist")}
                      for r in repos],
            "ecosystems": eco_list,
            "lineage": {"source_snapshot_id": self.snapshot_id, "source_snapshot_date": self.snapshot_date,
                        "as_of_activity_date": self.as_of, "activity_window": [self.window_start, self.as_of],
                        "source_tables": sorted(self.tables_used),
                        "github_api": {"authenticated": self.gh.authenticated, "calls_this_run": self.gh.calls},
                        "thresholds_config": str(CONFIG.relative_to(ROOT)),
                        "generated_at": datetime.now(timezone.utc), "attribution": ATTRIBUTION},
        }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="GitHub username(s) and/or email(s)")
    ap.add_argument("--out-dir", default=str(ROOT / "out" / "inspect"))
    ap.add_argument("--no-github", action="store_true", help="skip live GitHub calls (cache still used)")
    args = ap.parse_args()

    cfg = tomllib.loads(CONFIG.read_text())
    ins = Inspector(cfg, use_github=not args.no_github)
    print(f"snapshot {ins.snapshot_id}, activity as-of {ins.as_of}, "
          f"GitHub {'token' if ins.gh.authenticated else 'UNAUTHENTICATED (60 req/h)'}", file=sys.stderr)
    matches = {i: ins.match(i) for i in args.inputs}
    cap = cfg["matching"]["max_full_records_per_input"]
    all_ids = sorted({m["canonical_developer_id"] for ms in matches.values() if len(ms) <= cap for m in ms})
    print("matched: " + ", ".join(f"{i} -> {[m['canonical_developer_id'] for m in ms] if len(ms) <= cap else f'{len(ms)} ids (over cap)'}"
                                  for i, ms in matches.items()), file=sys.stderr)
    facts = ins.facts(all_ids) if all_ids else {}

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for inp, ms in matches.items():
        if len(ms) > cap:
            doc = {"input": inp, "match_count": len(ms),
                   "note": f"input matches {len(ms)} canonical developers (> {cap}); likely a placeholder email. "
                           "All candidate ids are listed; no full records built.",
                   "candidates": ms, "records": []}
        else:
            doc = {"input": inp, "match_count": len(ms),
                   "note": None if len(ms) <= 1 else "input matches several canonical developers; all are reported",
                   "records": [ins.build_record(inp, m, facts) for m in ms]}
        path = out_dir / (re.sub(r"[^A-Za-z0-9_.@+-]", "_", inp) + ".json")
        path.write_text(json.dumps(jsonable(doc), indent=2, ensure_ascii=False))
        print(f"wrote {path} ({len(doc['records'])} record(s), {len(ms)} match(es))", file=sys.stderr)


if __name__ == "__main__":
    main()
