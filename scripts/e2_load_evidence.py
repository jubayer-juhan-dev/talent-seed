#!/usr/bin/env python3
"""Load Tier-1 harvested evidence JSON into Neon's talent_evidence table.

Reads out/enrichment/p1_tier1_enriched.json (from scripts/e1_tier1_harvest.py)
and upserts one row per evidence item. Idempotent: re-runs update in place.

Run:  DATABASE_URL=... uv run scripts/e2_load_evidence.py
      (falls back to DATABASE_URL in .env)
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
IN_JSON = ROOT / "out" / "enrichment" / "p1_tier1_enriched.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS talent_evidence (
  evidence_id   TEXT PRIMARY KEY,
  talent_id     TEXT NOT NULL,
  concept_id    TEXT,
  concept_name  TEXT NOT NULL,
  concept_type  TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('FACT','INFERENCE','UNKNOWN')),
  usage_level   TEXT NOT NULL,
  confidence    NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  source        TEXT NOT NULL,
  note          TEXT,
  enriched_at   TIMESTAMPTZ NOT NULL,
  loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_talent_evidence_talent ON talent_evidence(talent_id);
CREATE INDEX IF NOT EXISTS idx_talent_evidence_concept ON talent_evidence(concept_id);
"""


def eid(talent_id, concept_id, usage, source):
    h = hashlib.sha1(
        f"{talent_id}|{concept_id}|{usage}|{source}".encode()
    ).hexdigest()[:16]
    return f"ev_{h}"


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        for line in open(ROOT / ".env"):
            if line.startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not db_url:
        sys.exit("no DATABASE_URL in env or .env")
    people = json.loads(open(IN_JSON).read())
    if not isinstance(people, list):
        people = list(people.values())

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(SCHEMA)
    cur.execute("SELECT concept_id FROM concepts")
    valid = {r[0] for r in cur.fetchall()}

    n_ins, bad_cids = 0, set()
    for p in people:
        tid = p["talent"]["person_id"]
        enriched_at = p.get("enriched_at")
        for e in p.get("evidence", []):
            cid = e.get("concept_id") or None
            if cid and cid not in valid:
                bad_cids.add(cid)
                cid = None
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_id, concept_name, concept_type,
                    status, usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (evidence_id) DO UPDATE SET
                     confidence=EXCLUDED.confidence, note=EXCLUDED.note,
                     enriched_at=EXCLUDED.enriched_at, loaded_at=now()""",
                (eid(tid, e.get("concept_id"), e["usage"], e["source"]),
                 tid, cid, e["concept"], e["type"], e["status"], e["usage"],
                 e["confidence"], e["source"], e.get("note"), enriched_at))
            n_ins += 1
    print(f"upserted {n_ins} evidence rows for {len(people)} people")
    if bad_cids:
        print("concept_ids not in ontology:", sorted(bad_cids))


if __name__ == "__main__":
    main()
