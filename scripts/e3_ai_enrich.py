#!/usr/bin/env python3
"""Stage 2 — LLM enrichment with GPT-6 Luna (OpenAI).

Reads Tier-1 harvested profiles, asks the model to infer roles, seniority and a
recruiter-readable summary, and writes the results into Neon. The model only ever
writes INFERENCE rows (status column) — it can never create a FACT.

Cost: ~$0.0005/person -> full P1 cohort (~4,332) is about $2.

Usage:
  OPENAI_API_KEY=sk-... uv run --with openai --with psycopg2-binary --with pydantic \
      python scripts/e3_ai_enrich.py [--limit 20] [--model gpt-6-luna]

Resumable: people already enriched by this model (llm_model match) are skipped.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
IN_JSON = ROOT / "out" / "enrichment" / "p1_tier1_enriched.json"

PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS talent_profiles (
  talent_id            TEXT PRIMARY KEY,
  summary              TEXT,
  seniority_band       TEXT CHECK (seniority_band IN
                         ('junior','mid','senior','staff','unknown')),
  seniority_confidence NUMERIC(3,2),
  llm_model            TEXT NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


class RoleInference(BaseModel):
    concept_id: str = Field(description="Ontology role concept id, e.g. PM.ROLE.0003")
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(description="One sentence, grounded in the profile data")


class Seniority(BaseModel):
    band: str = Field(description="junior | mid | senior | staff | unknown")
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class EnrichmentOutput(BaseModel):
    roles: list[RoleInference] = Field(
        description="Inferred roles, strongest first. Empty if no confident inference.")
    seniority: Seniority
    summary: str = Field(description="2-3 line recruiter-readable summary")


def db_url():
    u = os.environ.get("DATABASE_URL")
    if not u:
        for line in open(ROOT / ".env"):
            if line.startswith("DATABASE_URL="):
                u = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not u:
        sys.exit("no DATABASE_URL in env or .env")
    return u


def fmt_counted(d, n=10):
    """Format a {name: count} dict (or plain list) as 'a (3), b (2)'."""
    if not d:
        return "—"
    if isinstance(d, dict):
        items = sorted(d.items(), key=lambda kv: -kv[1])[:n]
        return ", ".join(f"{k} ({v})" for k, v in items)
    return ", ".join(str(x) for x in d[:n])


def get_top_repos(person_id, n=10):
    """Top repos by stars from the Tier-1 SQLite cache."""
    import sqlite3
    try:
        c = sqlite3.connect(ROOT / "data" / "tier1_github.sqlite")
        row = c.execute(
            "SELECT repos_json FROM github_raw WHERE person_id = ?", (person_id,)
        ).fetchone()
        if not row or not row[0]:
            return []
        repos = json.loads(row[0])
        repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)
        return repos[:n]
    except Exception:
        return []


def get_contribution_repos(person_id, n=15):
    """Top repos the person commits to (Electric Capital data in the DuckDB).

    Covers personal repos, org repos, and contributions to others' repos —
    anything with original commits, excluding inherited history.
    """
    import duckdb
    try:
        c = duckdb.connect(str(ROOT / "data" / "talent_seed.duckdb"), read_only=True)
        rows = c.execute(
            """SELECT repo_name, commits, active_days FROM talent_seed_repos
               WHERE person_id = ? AND NOT inherited_history
               ORDER BY commits DESC LIMIT ?""",
            (person_id, n),
        ).fetchall()
        c.close()
        return rows
    except Exception:
        return []


def build_prompt(person, valid_roles):
    t = person["talent"]
    gh = person.get("github_profile") or {}
    facts = [e["concept"] for e in person.get("evidence", []) if e["status"] == "FACT"]
    top_repos = get_top_repos(t["person_id"])
    contrib = get_contribution_repos(t["person_id"])
    contrib_line = ", ".join(f"{r[0]} ({r[1]} commits)" for r in contrib)
    repo_lines = "\n".join(
        f"- {r.get('full_name') or r.get('name')} "
        f"(stars {r.get('stargazers_count', 0)}, lang {r.get('language') or '?'}): "
        f"{(r.get('description') or '')[:120]}".strip()
        for r in top_repos
    )
    roles_list = "\n".join(f"- {cid}: {name}" for cid, name in valid_roles)
    return f"""You are classifying a crypto developer's GitHub profile into a talent ontology.

GitHub: {t.get('github')} ({t.get('name')})
Location: {gh.get('location') or '—'} | Blog: {gh.get('blog') or '—'} | \
Followers: {gh.get('followers', '?')} | Public repos: {gh.get('public_repos', '?')}
Top languages (repos): {fmt_counted(person.get('top_languages'))}
Top topics: {fmt_counted(person.get('top_topics'), 15)}
Top owned repos by stars:
{repo_lines or '—'}
Top contribution repos (commits to any repo incl. orgs, Electric Capital data):
{contrib_line or '—'}
Rules-derived skills (observed facts): {', '.join(facts[:20]) or '—'}

Valid role concept ids (pick ONLY from this list):
{roles_list}

Rules:
- Infer roles ONLY from the evidence above. Weigh owned repos AND contribution repos; heavy commits to a well-known project are strong evidence. If the signal is thin, return an empty roles list.
- concept_id must be one of the valid ids. Never invent one.
- confidence is your honest uncertainty, 0-1.
- Seniority band: junior | mid | senior | staff | unknown. Prefer unknown over a guess.
- Summary: 2-3 lines a recruiter can skim. No hype."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only enrich N people (0 = all)")
    ap.add_argument("--model", default="gpt-6-luna")
    a = ap.parse_args()

    from openai import OpenAI  # imported late so --help works without the dep
    import psycopg2

    client = OpenAI()  # reads OPENAI_API_KEY
    conn = psycopg2.connect(db_url())
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(PROFILE_SCHEMA)
    cur.execute(
        "SELECT concept_id, canonical_name FROM concepts WHERE concept_type = 'ROLE' "
        "ORDER BY concept_id"
    )
    valid_roles = cur.fetchall()
    if not valid_roles:
        # fall back to naming convention if the type column differs
        cur.execute(
            "SELECT concept_id, canonical_name FROM concepts "
            "WHERE concept_id LIKE 'PM.ROLE.%' ORDER BY concept_id"
        )
        valid_roles = cur.fetchall()
    print(f"{len(valid_roles)} role concepts loaded", flush=True)

    people = json.loads(open(IN_JSON).read())
    if not isinstance(people, list):
        people = list(people.values())
    cur.execute("SELECT talent_id FROM talent_profiles WHERE llm_model = %s", (a.model,))
    done = {r[0] for r in cur.fetchall()}
    todo = [p for p in people if p["talent"]["person_id"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} people to enrich with {a.model} ({len(done)} already done)",
          flush=True)

    for i, p in enumerate(todo, 1):
        tid = p["talent"]["person_id"]
        try:
            resp = client.responses.parse(
                model=a.model,
                input=[{"role": "user",
                        "content": build_prompt(p, valid_roles)}],
                text_format=EnrichmentOutput,
            )
            out = resp.output_parsed
        except Exception as ex:
            print(f"[{i}/{len(todo)}] {tid} LLM error: {ex}", flush=True)
            time.sleep(5)
            continue

        # roles -> INFERENCE rows in talent_evidence
        for r in out.roles:
            if not any(cid == r.concept_id for cid, _ in valid_roles):
                continue
            name = next(n for cid, n in valid_roles if cid == r.concept_id)
            eid = f"ev_llm_{a.model}_{tid}_{r.concept_id}".replace(":", "_")
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_id, concept_name, concept_type,
                    status, usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,%s,'ROLE','INFERENCE','OBSERVED_USAGE',%s,%s,%s,now())
                   ON CONFLICT (evidence_id) DO UPDATE SET
                     confidence=EXCLUDED.confidence, note=EXCLUDED.note,
                     enriched_at=now(), loaded_at=now()""",
                (eid, tid, r.concept_id, name, r.confidence,
                 f"llm:{a.model}", r.reasoning),
            )
        # seniority + summary -> talent_profiles
        cur.execute(
            """INSERT INTO talent_profiles
               (talent_id, summary, seniority_band, seniority_confidence, llm_model)
               VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (talent_id) DO UPDATE SET
                 summary=EXCLUDED.summary,
                 seniority_band=EXCLUDED.seniority_band,
                 seniority_confidence=EXCLUDED.seniority_confidence,
                 llm_model=EXCLUDED.llm_model, updated_at=now()""",
            (tid, out.summary, out.seniority.band, out.seniority.confidence, a.model),
        )
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] enriched {tid}: "
                  f"{len(out.roles)} roles, seniority {out.seniority.band}",
                  flush=True)


if __name__ == "__main__":
    main()
