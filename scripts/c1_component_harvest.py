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
  ... --components lib:a,lib:b   # only these components (re-scans repos that declare them)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
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
    for dirpath, dirnames, filenames in os.walk(clone, onerror=lambda e: None):
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
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r"^\s*([A-Za-z0-9_-]+)\s*=", txt, re.M):
                packages["cargo"].add(m.group(1))
        elif p.name == "go.mod":
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r"^\s*(github\.com/[\w./-]+)", txt, re.M):
                packages["go"].add(m.group(1))
        elif p.name in ("requirements.txt", "pyproject.toml"):
            try:
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r"^\s*([A-Za-z0-9_.-]+)", txt, re.M):
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


def declares(comp: dict, pkgs: dict) -> bool:
    """True when a repo's manifest packages ({eco: set}) include one of the component's packages."""
    return any(
        pkg in pkgs.get(eco, set()) or any(p.startswith(pkg + "/") for p in pkgs.get(eco, set()))
        for eco, plist in comp["packages"].items() for pkg in plist)


def ensure_clone(full_name: str, cache: sqlite3.Connection) -> Path | None:
    dest = CLONES / full_name.replace("/", "__")
    if dest.exists():
        return dest
    if not dest.exists():
        url = f"https://github.com/{full_name}.git"
        try:
            r = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", url, str(dest)],
                               capture_output=True, timeout=180)
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            shutil.rmtree(dest, ignore_errors=True)
            cache.execute("INSERT OR REPLACE INTO scanned VALUES (?, ?)", (full_name, "clone-failed"))
            cache.commit()
            return None
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--own-repos", type=int, default=3)
    ap.add_argument("--components", default="",
                    help="comma-separated component ids: harvest and write only these, and re-scan "
                         "cached repos whose manifests declare them (cached import hits predate them)")
    a = ap.parse_args()
    only = {c.strip() for c in a.components.split(",") if c.strip()}
    unknown = only - set(BY_ID)
    if unknown:
        sys.exit(f"unknown component ids: {sorted(unknown)}")
    targets = [c for c in COMPONENTS if not only or c["id"] in only]

    import duckdb
    import psycopg2

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CLONES.mkdir(parents=True, exist_ok=True)
    cache = sqlite3.connect(CACHE_DIR / "cache.sqlite", timeout=180)
    cache.execute("CREATE TABLE IF NOT EXISTS scanned (repo TEXT PRIMARY KEY, result TEXT)")
    cache.execute("CREATE TABLE IF NOT EXISTS repo_scan (repo TEXT PRIMARY KEY, json TEXT)")
    cache.commit()
    if only:
        # A cached scan only holds import hits for the components registered when it ran, so
        # repos that declare a target component are dropped from the cache and cloned again.
        stale = []
        for repo, js in cache.execute("SELECT repo, json FROM repo_scan").fetchall():
            pkgs = {eco: set(names) for eco, names in json.loads(js)["packages"].items()}
            if any(declares(c, pkgs) for c in targets):
                stale.append(repo)
        cache.executemany("DELETE FROM repo_scan WHERE repo = ?", [(r,) for r in stale])
        cache.commit()
        print(f"components: {sorted(only)}; cached repos to re-scan: {len(stale)}")

    d = duckdb.connect(str(ROOT / "data" / "talent_seed.duckdb"), read_only=True)
    import csv as _csv
    cohort = set()
    cohort_files = os.environ.get(
        "C1_COHORT_FILES", "p1_cohort.csv,p1_rest_cohort.csv").split(",")
    cohort_files = [n.strip() for n in cohort_files if n.strip()]
    for name in cohort_files:
        with open(ROOT / "exports" / name) as f:
            cohort |= {r["person_id"] for r in _csv.DictReader(f)}
    rows = d.execute(
        """SELECT person_id, github_login, commit_count FROM talent_seed
           WHERE github_login IS NOT NULL AND github_login NOT LIKE '%[bot]'
           ORDER BY commit_count DESC""").fetchall()
    # Batch-2 talents sit at the tail of the commit ranking; when their
    # github_login was resolved later (m5), talent_seed.github_login can be
    # NULL while the cohort CSV carries the login. Append any cohort member
    # missing from the ranked list so offset/limit covers ALL of P1.
    seen = {t[0] for t in rows}
    talents = [t for t in rows if t[0] in cohort]
    import csv as _csv2
    login_by_id = {}
    for name in cohort_files:
        with open(ROOT / "exports" / name) as f:
            for r in _csv2.DictReader(f):
                login_by_id[r["person_id"]] = r.get("github_login") or ""
    for pid in sorted(cohort - seen):
        cc = d.execute("SELECT commit_count FROM talent_seed WHERE person_id = ?",
                       [pid]).fetchone()
        talents.append((pid, login_by_id.get(pid) or None, cc[0] if cc else 0))
    talents = talents[a.offset: a.offset + a.limit]
    print(f"pilot: {len(talents)} talents")

    s1 = sqlite3.connect(ROOT / "data" / "tier1_github.sqlite")
    results = {}  # (talent_id, comp_id) -> (level, proof)

    def bump(tid, cid, level, proof):
        if only and cid not in only:
            return
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
                try:
                    scan = scan_repo(dest)
                except Exception:
                    scan = {"packages": {"npm": [], "cargo": [], "go": [], "pypi": []},
                            "imports": {}}
                import shutil
                shutil.rmtree(dest, ignore_errors=True)
                cache.execute("INSERT OR REPLACE INTO repo_scan VALUES (?, ?)",
                              (full, json.dumps(scan)))
                cache.execute("INSERT OR REPLACE INTO scanned VALUES (?, 'ok')", (full,))
                cache.commit()
            pkgs = {eco: set(names) for eco, names in scan["packages"].items()}
            for comp in targets:
                declared = declares(comp, pkgs)
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
    for comp in targets:
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
