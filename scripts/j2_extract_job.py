#!/usr/bin/env python3
"""j2 — job requirement extraction (Job Graph, ProspectMind).

Paste a job posting in; ontology requirements come out.

  uv run --with openai --with psycopg2-binary --with pydantic python \
    scripts/j2_extract_job.py --title "Senior Solidity Developer" \
    --company "Uniswap" --location "Remote" --file posting.txt

Rules first (title keywords -> role FACT), then one Luna call for the fuzzy
middle: requirements buried in prose, required vs nice-to-have, seniority.
Every requirement row carries an evidence quote from the posting.
Concept ids come ONLY from the ontology; unmapped terms are reported as
growth candidates and NOT stored as requirements.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL_TAG = "llm:gpt-6-luna-job"

# deterministic title -> role concept hints (FACT by construction)
TITLE_ROLE_HINTS = [
    (re.compile(r"solidity|smart contract", re.I), "Smart Contract Developer"),
    (re.compile(r"full[\s-]?stack", re.I), "Full-Stack Developer"),
    (re.compile(r"front[\s-]?end", re.I), "Frontend Developer"),
    (re.compile(r"back[\s-]?end", re.I), "Backend Developer"),
    (re.compile(r"devops|sre|site reliability", re.I), "DevOps Engineer"),
    (re.compile(r"data engineer", re.I), "Data Engineer"),
    (re.compile(r"protocol", re.I), "Protocol Engineer"),
    (re.compile(r"security|auditor", re.I), "Security Engineer"),
]


class ReqOut(BaseModel):
    concept_id: str = Field(description="ontology concept id from the valid list")
    concept_name: str
    concept_type: str = Field(description="ROLE|SKILL|TOOL|SYSTEM|KNOWLEDGE")
    requirement: str = Field(description="required|nice_to_have")
    confidence: float
    evidence_text: str = Field(description="short exact quote from the posting")


class JobExtraction(BaseModel):
    seniority_band: str = Field(description="junior|mid|senior|staff|unknown")
    requirements: list[ReqOut]
    growth_candidates: list[str] = Field(
        description="terms the posting requires that are NOT in the ontology list")


def load_concepts(cur):
    cur.execute("SELECT concept_id, canonical_name, concept_type FROM concepts ORDER BY concept_type, canonical_name")
    return cur.fetchall()


def extract_job(cur, client, model, title, company, location, description, source="manual", url=None):
    concepts = load_concepts(cur)
    valid = {cid: (name, ctype) for cid, name, ctype in concepts}
    concepts_list = "\n".join(f"- {cid}: {name} ({ctype})" for cid, name, ctype in concepts)

    job_id = "job:" + hashlib.sha1(
        f"{source}|{title}|{company or ''}|{description[:500]}".encode()).hexdigest()[:16]

    prompt = f"""You are extracting hiring requirements from a job posting into a talent ontology.

Job title: {title}
Company: {company or '—'}
Location: {location or '—'}

Posting:
\"\"\"
{description[:12000]}
\"\"\"

Valid concept ids (pick ONLY from this list):
{concepts_list}

Rules:
- Extract what the CANDIDATE must have. 'You will use X', 'experience with X', 'requirements: X'
  count. An explicit Skills/Tags section on the posting (e.g. 'Skills: TypeScript, React, Docker')
  counts — the poster listed those skills deliberately. Pure company-stack prose
  ('our stack includes X' with no candidate demand) does NOT count.
- requirement = required | nice_to_have (things under 'bonus', 'nice to have', 'plus' are nice_to_have).
- Every requirement needs an evidence_text: a short exact quote from the posting.
- confidence is your honest uncertainty, 0-1.
- seniority_band: junior|mid|senior|staff|unknown — from years/leadership signals only.
- Terms the posting requires that are not in the concept list go to growth_candidates
  (names only). Never invent a concept id.
"""
    resp = client.responses.parse(
        model=model,
        input=[{"role": "user", "content": prompt}],
        text_format=JobExtraction,
    )
    out = resp.output_parsed

    rows = []
    # rules pass: title role hints (FACT)
    for pat, role_name in TITLE_ROLE_HINTS:
        if pat.search(title):
            hit = next(((cid, n, t) for cid, n, t in concepts
                        if n.lower() == role_name.lower()), None)
            if hit:
                rows.append((hit[0], hit[1], hit[2], "required", "FACT", 1.0,
                             f"title: {title}", "rules:jobtitle"))
            break

    seen = {(r[1], r[3]) for r in rows}
    for r in out.requirements:
        if r.concept_id not in valid:
            continue  # hallucinated id — growth candidates carry the name instead
        name, ctype = valid[r.concept_id]
        req = r.requirement if r.requirement in ("required", "nice_to_have") else "required"
        if (name, req) in seen:
            continue
        seen.add((name, req))
        rows.append((r.concept_id, name, ctype, req, "INFERENCE",
                     max(0.0, min(1.0, r.confidence)), r.evidence_text[:300], MODEL_TAG))

    # persist
    from viewer_api.location_norm import normalize as norm_loc
    _, country = norm_loc(location) if location else (None, None)
    cur.execute(
        """INSERT INTO jobs (job_id, title, company, location_text, location_country,
                             source, description, url, active)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE)
           ON CONFLICT (job_id) DO UPDATE SET title=EXCLUDED.title,
             company=EXCLUDED.company, description=EXCLUDED.description, active=TRUE""",
        (job_id, title, company, location, country, source, description, url))
    cur.execute("DELETE FROM job_requirements WHERE job_id = %s", (job_id,))
    for cid, name, ctype, req, status, conf, ev, src in rows:
        cur.execute(
            """INSERT INTO job_requirements
               (job_id, concept_id, concept_name, concept_type, requirement,
                status, confidence, evidence_text, source)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT DO NOTHING""",
            (job_id, cid, name, ctype, req, status, conf, ev, src))
    return job_id, rows, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--company", default="")
    ap.add_argument("--location", default="")
    ap.add_argument("--url", default=None)
    ap.add_argument("--source", default="manual")
    ap.add_argument("--file", required=True, help="posting text file")
    ap.add_argument("--model", default="gpt-6-luna")
    a = ap.parse_args()

    import psycopg2
    from openai import OpenAI

    description = Path(a.file).read_text(encoding="utf-8")
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    cur = conn.cursor()
    client = OpenAI()

    job_id, rows, out = extract_job(cur, client, a.model, a.title, a.company,
                                    a.location, description, a.source, a.url)
    print(f"{job_id} | seniority: {out.seniority_band}")
    for cid, name, ctype, req, status, conf, ev, src in rows:
        print(f"  [{req:11s}] {ctype:9s} {name} ({status} {conf:.2f}) — {ev[:80]}")
    if out.growth_candidates:
        print("  growth candidates (not in ontology):", ", ".join(out.growth_candidates))
    print(f"{len(rows)} requirements stored")


if __name__ == "__main__":
    main()
