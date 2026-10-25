#!/usr/bin/env python3
"""Re-classify the Tier-1 GitHub cache for a chosen set of concepts and load
only their evidence into Neon's talent_evidence table.

Reusable version of the one-off loader used for PM.SKILL.0013. No GitHub
re-scan: reads data/tier1_github.sqlite (github_raw, api_status=200), gets
each person's Talent Seed row via e1's seed_rows(), runs
enrichment.tier1.classify() under the CURRENT topic/language maps, keeps
only evidence whose concept_id is in --concepts, and upserts it with e2's
evidence ids and upsert SQL. enriched_at is the cache row's fetched_at.
Everything loads in one transaction; --dry-run prints the would-be
per-concept people/row counts without writing.

Run:  uv run --with psycopg2-binary python scripts/e6_reclassify_cache.py \
          --concepts PM.SKILL.0014,PM.TOOL.0009 [--dry-run]
      (DATABASE_URL from env or .env, same fallback as e2)
"""
import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from enrichment import tier1  # noqa: E402


def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


e1 = load_mod("e1_tier1_harvest", ROOT / "scripts" / "e1_tier1_harvest.py")
e2 = load_mod("e2_load_evidence", ROOT / "scripts" / "e2_load_evidence.py")

CACHE = ROOT / "data" / "tier1_github.sqlite"

UPSERT = """INSERT INTO talent_evidence
           (evidence_id, talent_id, concept_id, concept_name, concept_type,
            status, usage_level, confidence, source, note, enriched_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (evidence_id) DO UPDATE SET
             confidence=EXCLUDED.confidence, note=EXCLUDED.note,
             enriched_at=EXCLUDED.enriched_at, loaded_at=now()"""


def db_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        for line in open(ROOT / ".env"):
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url:
        sys.exit("no DATABASE_URL in env or .env")
    return url


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concepts", required=True,
                    help="comma-separated concept ids to (re)load evidence for")
    ap.add_argument("--dry-run", action="store_true",
                    help="print per-concept counts, write nothing")
    a = ap.parse_args()
    wanted = [c.strip() for c in a.concepts.split(",") if c.strip()]
    want = set(wanted)

    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    cur.execute("SELECT concept_id FROM concepts WHERE concept_id = ANY(%s)",
                (wanted,))
    found = {r[0] for r in cur.fetchall()}
    missing = [c for c in wanted if c not in found]
    if missing:
        sys.exit(f"concept ids not in Neon concepts table: {missing}")

    concepts = tier1.load_concepts()
    not_in_yaml = [c for c in wanted if c not in concepts]
    if not_in_yaml:
        sys.exit(f"concept ids not in ontology seed YAML: {not_in_yaml}")

    cache = sqlite3.connect(CACHE)
    pids = [r[0] for r in cache.execute(
        "SELECT person_id FROM github_raw WHERE api_status = 200 "
        "ORDER BY person_id")]

    people_counts = defaultdict(set)
    row_counts = Counter()
    batch = []
    n_people = 0
    skipped = 0
    CHUNK = 500
    for i in range(0, len(pids), CHUNK):
        chunk = pids[i:i + CHUNK]
        rows = e1.seed_rows(chunk)
        marks = ",".join("?" * len(chunk))
        raw = {r[0]: r[1:] for r in cache.execute(
            f"SELECT person_id, user_json, repos_json, fetched_at "
            f"FROM github_raw WHERE person_id IN ({marks})", chunk)}
        for pid in chunk:
            if pid not in rows or pid not in raw:
                skipped += 1
                continue
            user_json, repos_json, fetched_at = raw[pid]
            user = json.loads(user_json)
            res = tier1.classify(rows[pid], user,
                                 json.loads(repos_json) if repos_json else [],
                                 concepts)
            n_people += 1
            for e in res["evidence"]:
                cid = e.get("concept_id")
                if cid not in want:
                    continue
                people_counts[cid].add(pid)
                row_counts[cid] += 1
                if not a.dry_run:
                    batch.append((
                        e2.eid(pid, cid, e["usage"], e["source"]),
                        pid, cid, e["concept"], e["type"], e["status"],
                        e["usage"], e["confidence"], e["source"],
                        e.get("note"), fetched_at))
        if batch:
            cur.executemany(UPSERT, batch)
            batch.clear()

    if a.dry_run:
        conn.rollback()
    else:
        conn.commit()
    conn.close()

    mode = "DRY-RUN (nothing written)" if a.dry_run else "LOADED"
    print(f"{mode}: classified {n_people} people "
          f"({skipped} skipped: no seed row or cache row)")
    tot_people = set()
    tot_rows = 0
    for cid in wanted:
        ppl = people_counts.get(cid, set())
        tot_people |= ppl
        tot_rows += row_counts.get(cid, 0)
        print(f"  {cid}: {len(ppl)} people, {row_counts.get(cid, 0)} rows")
    print(f"  TOTAL: {len(tot_people)} distinct people, {tot_rows} rows "
          f"across {len(wanted)} concepts")


if __name__ == "__main__":
    main()
