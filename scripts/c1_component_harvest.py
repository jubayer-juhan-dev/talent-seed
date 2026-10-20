#!/usr/bin/env python3
"""c1 — component-level harvest (ProspectMind Phase 2 pilot).

For each pilot talent:
  CONTRIBUTOR_USAGE — talent has commits in a registered library's own repo
                      (from the DuckDB, no fetching).
  OBSERVED_USAGE    — a registered library is imported in the talent's own
                      repos (shallow clone + source scan).
  DECLARED_USAGE    — a registered library sits in a manifest, never imported.

Writes code_components + library_usage_evidence in Neon and upgrades
talent_evidence with concept FACTs at the found level. Clones are cached
under data/component_cache/ and scanned once per repo.

  uv run --with duckdb --with psycopg2-binary python scripts/c1_component_harvest.py --limit 200
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from enrichment.components import BY_ID, BY_REPO, COMPONENTS  # noqa: E402

CACHE_DIR = ROOT / "data" / "component_cache"
CLONES = CACHE_DIR / "clones"
MANIFESTS = {"package.json", "Cargo.toml", "go.mod", "requirements.txt", "pyproject.toml"}
SRC_EXT = {".sol", ".ts", ".tsx", "js", ".jsx", ".go", ".rs", ".py"}
SKIP_DIRS = {".git", "node_modules", "vendor", "target", "dist", "build", ".next"}
MAX_REPO_KB = 150_000
LEVEL_RANK = {"DECLARED_USAGE": 1, "OBSERVED_USAGE": 2, "CONTRIBUTOR_USAGE": 3}


def scan_repo(clone: Path) -> dict:
    """{packages: {eco: set(names)}, imports_hit: {comp_id: example_file}}"""
    packages: dict[str, set] = {"npm": set(), "cargo": set(), "go": set(), "pypi": set()}
    files = []
    for dirpath, dirnames, filenames in os.walk(clone):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            files.append(p)
    for p in files:
        if p.name == "package.json":
            try:
                d = json.loads(p.read_text(errors="ignore"))
                for sec in ("dependencies", "devDependencies", "peerDependencies"):
                    packages["npm"] |= set((d.get(sec) or {}).keys())
            except Exception:
                pass
        elif p.name == "Cargo.toml":
            txt = p.read_text(errors="ignore")
            for m in re.finditer(r"^\s*([A-Za-z0-9_-]+)\s*=", txt, re.M):
                packages["cargo"].add(m.group(1))
        elif p.name == "go.mod":
            for m in re.finditer(r"^\s*(github\.com/[\w./-]+)", p.read_text(errors="ignore"), re.M):
                packages["go"].add(m.group(1))
        elif p.name in ("requirements.txt", "pyproject.toml"):
            for m in re.finditer(r"^\s*([A-Za-z0-9_.-]+)", p.read_text(errors="ignore"), re.M):
                packages["pypi"].add(m.group(1).lower())
    hits: dict[str, str] = {}
    pats = [(c["id"], [re.compile(rx) for rx in c["imports"]]) for c in COMPONENTS if c["imports"]]
    scanned = 0
    for p in files:
        if scanned >= 500:
            break
        if p.suffix not in SRC_EXT and p.suffix != ".js":
            continue
        try:
            if p.stat().st_size > 300_000:
                continue
            txt = p.read_text(errors="ignore")
        except Exception:
            continue
        scanned += 1
        for cid, regexes in pats:
            if cid in hits:
                continue
            if any(rx.search(txt) for rx in regexes):
                hits[cid] = str(p.relative_to(clone))
    return {"packages": {k: sorted(v) for k, v in packages.items()}, "imports": hits}


def ensure_clone(full_name: str, cache: sqlite3.Connection) -> Path | None:
    dest = CLONES / full_name.replace("/", "__")
    if dest.exists():
        return dest
    if not dest.exists():
        url = f"https://github.com/{full_name}.git"
        r = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
                           capture_output=True, timeout=180)
        if r.returncode != 0:
            cache.execute("INSERT OR REPLACE INTO scanned VALUES (?, ?)", (full_name, "clone-failed"))
            cache.commit()
            return None
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--own-repos", type=int, default=3)
    a = ap.parse_args()

    import duckdb
    import psycopg2

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CLONES.mkdir(parents=True, exist_ok=True)
    cache = sqlite3.connect(CACHE_DIR / "cache.sqlite")
    cache.execute("CREATE TABLE IF NOT EXISTS scanned (repo TEXT PRIMARY KEY, result TEXT)")
    cache.execute("CREATE TABLE IF NOT EXISTS repo_scan (repo TEXT PRIMARY KEY, json TEXT)")
    cache.commit()

    d = duckdb.connect(str(ROOT / "data" / "talent_seed.duckdb"), read_only=True)
    import csv as _csv
    cohort = set()
    for name in ("p1_cohort.csv", "p1_rest_cohort.csv"):
        with open(ROOT / "exports" / name) as f:
            cohort |= {r["person_id"] for r in _csv.DictReader(f)}
    talents = [t for t in d.execute(
        """SELECT person_id, github_login, commit_count FROM talent_seed
           WHERE github_login IS NOT NULL AND github_login NOT LIKE '%[bot]'
           ORDER BY commit_count DESC""").fetchall()
        if t[0] in cohort][a.offset: a.offset + a.limit]
    print(f"pilot: {len(talents)} talents")

    s1 = sqlite3.connect(ROOT / "data" / "tier1_github.sqlite")
    results = {}  # (talent_id, comp_id) -> (level, proof)

    def bump(tid, cid, level, proof):
        key = (tid, cid)
        if key not in results or LEVEL_RANK[level] > LEVEL_RANK[results[key][0]]:
            results[key] = (level, proof)

    for tid, login, _cc in talents:
        # CONTRIBUTOR: commits in a registered repo (DuckDB)
        for repo_name, commits in d.execute(
                "SELECT repo_name, commits FROM talent_seed_repos WHERE person_id = ?",
                [tid]).fetchall():
            comp = BY_REPO.get((repo_name or "").lower())
            if comp:
                bump(tid, comp["id"], "CONTRIBUTOR_USAGE",
                     f"{commits} commits to {repo_name}")
        # OWN repos: manifests + imports
        row = s1.execute("SELECT repos_json FROM github_raw WHERE person_id = ?", (tid,)).fetchone()
        if not row or not row[0]:
            continue
        try:
            repos = json.loads(row[0])
        except Exception:
            continue
        own = [r for r in repos
               if (r.get("full_name") or "").split("/")[0].lower() == (login or "").lower()
               and not r.get("fork")]
        own.sort(key=lambda r: -(r.get("stargazers_count") or 0))
        for r in own[: a.own_repos]:
            full = r.get("full_name")
            if not full or (r.get("size") or 0) > MAX_REPO_KB:
                continue
            cached = cache.execute("SELECT json FROM repo_scan WHERE repo = ?", (full,)).fetchone()
            if cached:
                scan = json.loads(cached[0])
            else:
                dest = ensure_clone(full, cache)
                if dest is None:
                    continue
                scan = scan_repo(dest)
                import shutil
                shutil.rmtree(dest, ignore_errors=True)
                cache.execute("INSERT OR REPLACE INTO repo_scan VALUES (?, ?)",
                              (full, json.dumps(scan)))
                cache.execute("INSERT OR REPLACE INTO scanned VALUES (?, 'ok')", (full,))
                cache.commit()
            pkgs = {eco: set(names) for eco, names in scan["packages"].items()}
            for comp in COMPONENTS:
                declared = any(
                    pkg in pkgs.get(eco, set()) or
                    any(p.startswith(pkg + "/") for p in pkgs.get(eco, set()))
                    for eco, plist in comp["packages"].items() for pkg in plist)
                if comp["id"] in scan["imports"]:
                    bump(tid, comp["id"], "OBSERVED_USAGE",
                         f"import in {full}:{scan['imports'][comp['id']]}")
                elif declared:
                    bump(tid, comp["id"], "DECLARED_USAGE", f"manifest of {full}")

    print(f"usage rows: {len(results)}")
    from collections import Counter
    print(Counter(lvl for lvl, _ in results.values()))

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    concept_names = {}
    cur.execute("SELECT concept_id, canonical_name, concept_type FROM concepts")
    for cid, nm, tp in cur.fetchall():
        concept_names[cid] = (nm, tp)
    today = date.today().isoformat()
    for comp in COMPONENTS:
        repo = comp["repos"][0] if comp["repos"] else ""
        cur.execute(
            """INSERT INTO code_components (component_id, repository_id, revision, path, languages)
               VALUES (%s, %s, '', '', '{}') ON CONFLICT (component_id) DO NOTHING""",
            (comp["id"], f"github:{repo}"))
    n = 0
    for (tid, cid), (level, proof) in results.items():
        if level == "DECLARED_USAGE":
            level = "DECLARED"  # library_usage_evidence CHECK uses DECLARED
        comp = BY_ID[cid]
        eco, pkg = ("", "")
        for e, plist in comp["packages"].items():
            if plist:
                eco, pkg = e, plist[0]
                break
        eid = "comp:" + hashlib.sha1(f"{tid}|{cid}|{level}".encode()).hexdigest()[:24]
        cur.execute(
            """INSERT INTO library_usage_evidence
               (evidence_id, talent_id, component_id, package_ecosystem, package_name,
                usage_level, evidence_url, observed_date, confidence, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1.0,'FACT')
               ON CONFLICT (evidence_id) DO NOTHING""",
            (eid, tid, cid, eco, pkg, level, proof[:500], today))
        for concept_id in comp["concepts"]:
            nm, tp = concept_names.get(concept_id, (concept_id, "SKILL"))
            teid = hashlib.sha1(f"{tid}|{concept_id}|components:c1|{level}".encode()).hexdigest()
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_id, concept_name, concept_type, status,
                    usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,%s,%s,'FACT',%s,1.0,'components:c1',%s,now())
                   ON CONFLICT (evidence_id) DO NOTHING""",
                (teid, tid, concept_id, nm, tp, level,
                 f"{comp['name']} — {level}: {proof}"[:300]))
            n += 1
    print(f"talent_evidence upgrade rows attempted: {n}")


if __name__ == "__main__":
    main()
