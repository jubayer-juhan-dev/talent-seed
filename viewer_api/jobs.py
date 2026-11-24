"""Job Graph (ProspectMind): jobs, requirements, and j3 matching.

Matching is deterministic math over Neon tables — no LLM at query time.
Score per spec v0.4 proximity: S_d = sum(a_t * m(t,E)) / sum(a_t), with
a_t = 1.0 (required) / 0.4 (nice_to_have) and m from the talent's best
evidence for concept t: FACT observed+ = 1.0, FACT declared = 0.7,
INFERENCE = its confidence, missing = 0.
"""
from __future__ import annotations

import re

from . import settings

REQ_WEIGHT = {"required": 1.0, "nice_to_have": 0.4}

# evidence that gives a concept coverage > 0 in match() (UNKNOWN and zero-confidence rows don't)
POSITIVE_EVIDENCE = "(e.status = 'FACT' OR (e.status = 'INFERENCE' AND COALESCE(e.confidence, 0) > 0))"


def _conn():
    import psycopg2
    return psycopg2.connect(settings.NEON_URL, connect_timeout=8)


def _coverage(status, usage_level, confidence):
    if status == "FACT":
        if usage_level and "DECLARED" in usage_level:
            return 0.7
        return 1.0
    if status == "INFERENCE":
        return confidence if confidence is not None else 0.0
    return 0.0


def list_jobs():
    conn = _conn()
    try:
        cur = conn.cursor()
        # matches_count mirrors match(): talents in the evidence pool with any
        # evidence of positive coverage on one of the job's concepts.
        cur.execute(
            """SELECT j.job_id, j.title, j.company, j.location_text, j.location_country,
                      j.source, j.posted_at, j.fetched_at,
                      (SELECT COUNT(*) FROM job_requirements r WHERE r.job_id = j.job_id)
                          AS requirements_count,
                      (SELECT COUNT(*) FROM job_requirements r
                        WHERE r.job_id = j.job_id AND r.requirement = 'required') AS required_count,
                      (SELECT COUNT(*) FROM job_requirements r
                        WHERE r.job_id = j.job_id AND r.requirement = 'nice_to_have')
                          AS nice_to_have_count,
                      (SELECT COUNT(DISTINCT e.talent_id) FROM job_requirements r
                         JOIN talent_evidence e ON e.concept_id = r.concept_id
                        WHERE r.job_id = j.job_id
                          AND """ + POSITIVE_EVIDENCE + """)
                          AS matches_count
               FROM jobs j WHERE j.active ORDER BY j.fetched_at DESC""")
        cols = [d.name for d in cur.description]
        out = []
        for row in cur.fetchall():
            j = dict(zip(cols, row))
            j["posted_at"] = str(j["posted_at"])[:10] if j["posted_at"] else None
            j["created_at"] = str(j.pop("fetched_at"))[:10] if j.get("fetched_at") else None
            out.append(j)
        return out
    finally:
        conn.close()


def list_concepts():
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT k.concept_id, k.canonical_name AS name, k.concept_type AS type, k.definition,
                      COALESCE(k.aliases, ARRAY[]::text[]) AS aliases,
                      COUNT(DISTINCT e.talent_id) AS talents
               FROM concepts k LEFT JOIN talent_evidence e ON e.concept_id = k.concept_id
                    AND """ + POSITIVE_EVIDENCE + """
               WHERE k.status = 'ACTIVE'
               GROUP BY 1, 2, 3, 4, 5 ORDER BY k.concept_type, k.canonical_name""")
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def get_job(job_id):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT job_id, title, company, location_text, location_country, remote,
                      url, source, description, posted_at, active
               FROM jobs WHERE job_id = %s""", (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d.name for d in cur.description]
        job = dict(zip(cols, row))
        job["posted_at"] = str(row[9])[:10] if row[9] else None
        cur.execute(
            """SELECT concept_id, concept_name, concept_type, requirement, status,
                      confidence, evidence_text, source
               FROM job_requirements WHERE job_id = %s
               ORDER BY requirement, concept_type, concept_name""", (job_id,))
        rcols = [d.name for d in cur.description]
        job["requirements"] = [dict(zip(rcols, r)) for r in cur.fetchall()]
        return job
    finally:
        conn.close()


def _pool_ids(cur, pool):
    if pool == "ai":
        cur.execute("SELECT talent_id FROM talent_profiles WHERE llm_model LIKE 'gpt-%'")
    else:
        cur.execute("SELECT DISTINCT talent_id FROM talent_evidence")
    return [r[0] for r in cur.fetchall()]


def add_people(con, out):
    """Fill name, login, cohort and country on match() items from talent_seed (DuckDB connection `con`)."""
    ids = [r["talent_id"] for r in out["items"]]
    people = {}
    if ids:
        # one batched lookup: per-row queries cost ~50ms each on talent_seed
        people = {row[0]: row[1:] for row in con.execute(
            "SELECT person_id, display_name, github_login, github_user_id, priority_cohort, country"
            f" FROM talent_seed WHERE person_id IN ({','.join('?' * len(ids))})", ids).fetchall()}
    for r in out["items"]:
        if r["talent_id"] in people:
            (r["name"], r["github_login"], r["github_user_id"],
             r["priority_cohort"], r["country"]) = people[r["talent_id"]]
    return out

def add_enrichment_flag(out):
    """Set ai_enriched (+ ai_enriched_by) on match() items from the ai_enrichment flag table.

    The flag is the formal AI-enrichment mark (set via set_ai_enriched / submit_enrichment).
    Most talents have evidence but are NOT flagged, so this must come from the table,
    never inferred from evidence."""
    from . import enrichment
    ids = [r['talent_id'] for r in out['items']]
    found = enrichment.lookup(ids)
    for r in out['items']:
        hit = found.get(r['talent_id'])
        r['ai_enriched'] = hit is not None
        if hit:
            r['ai_enriched_by'] = hit[1]
    return out

def add_readiness(con, out):
    """Add item["readiness"] (email yes/no + count, x_handle, linkedin_url, telegram yes/no) to match() items.

    Sources: DuckDB talent_seed_contact_points (real, non-placeholder, non-noreply emails), the e4 outreach scrape
    out/enrichment/outreach_candidates.jsonl (x / linkedin / telegram channels), and the tier-1 GitHub cache
    (twitter_username, linkedin). Email addresses are only counted, never returned."""
    import json
    from . import github_profile
    ids = [r["talent_id"] for r in out["items"]]
    counts, e4 = {}, {}
    if ids:
        counts = dict(con.execute(
            "SELECT person_id, count(*) FROM talent_seed_contact_points WHERE type = 'EMAIL'"
            " AND NOT coalesce(is_github_noreply, false) AND NOT coalesce(is_placeholder, false)"
            f" AND person_id IN ({','.join('?' * len(ids))}) GROUP BY 1", ids).fetchall())
        want = set(ids)
        path = settings.ROOT / "out" / "enrichment" / "outreach_candidates.jsonl"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if not any(pid in line for pid in want):
                        continue
                    d = json.loads(line)
                    if d.get("person_id") in want:
                        e4[d["person_id"]] = d.get("channels") or []
    for r in out["items"]:
        tid = r["talent_id"]
        chans = {}
        for c in e4.get(tid, []):
            chans.setdefault(c.get("channel"), c.get("url"))
        gh = github_profile.fetch(tid) or {}
        x = chans.get("x") or gh.get("x_url")
        handle = None
        if x:
            m = re.search(r"(?:twitter|x)\.com/@?([A-Za-z0-9_]+)", x)
            handle = "@" + m.group(1) if m else None
        n = int(counts.get(tid, 0))
        r["readiness"] = {
            "email": {"has": "yes" if n else "no", "count": n},
            "x_handle": handle or gh.get("x_handle"),
            "linkedin_url": chans.get("linkedin") or gh.get("linkedin_url"),
            "telegram": "yes" if chans.get("telegram") else "no",
        }
    return out


def match_text(description, title="", company="", limit=20, pool="all"):
    """Raw job text -> the same j2 ontology extraction match_job's jobs go through (scripts/j2_extract_job.py,
    stored like POST /api/jobs does) -> match() with the same scoring."""
    import os
    import sys
    import psycopg2
    from openai import OpenAI
    if str(settings.ROOT) not in sys.path:
        sys.path.insert(0, str(settings.ROOT))
    from scripts.j2_extract_job import extract_job
    env = settings.ROOT / ".env"
    if env.exists() and not os.environ.get("OPENAI_API_KEY"):
        for line in env.read_text().splitlines():
            if line.startswith("OPENAI_API_KEY="):
                os.environ["OPENAI_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    conn = psycopg2.connect(settings.NEON_URL, connect_timeout=8)
    conn.autocommit = True
    try:
        # identical text already extracted (any source): reuse its requirements instead of another LLM call
        cur = conn.cursor()
        cur.execute("""SELECT j.job_id FROM jobs j WHERE j.description = %s
                       AND EXISTS (SELECT 1 FROM job_requirements r WHERE r.job_id = j.job_id AND r.concept_id IS NOT NULL)
                       ORDER BY j.active DESC, j.fetched_at DESC LIMIT 1""", (description,))
        hit = cur.fetchone()
        if hit:
            cur.execute("""SELECT concept_id, concept_name, concept_type, requirement FROM job_requirements
                           WHERE job_id = %s AND concept_id IS NOT NULL""", (hit[0],))
            out = match(hit[0], pool=pool, limit=limit)
            out.update(job_id=hit[0], reused_extraction=True, growth_candidates=[],
                       requirements=[{"concept_id": r[0], "concept_name": r[1], "requirement": r[3]}
                                     for r in cur.fetchall()])
            return out
        job_id, rows, extraction = extract_job(conn.cursor(), OpenAI(), "gpt-6-luna", title or "Untitled role",
                                               company, "", description, "manual", None)
    finally:
        conn.close()
    out = match(job_id, pool=pool, limit=limit)
    out["job_id"] = job_id
    out["requirements"] = [{"concept_id": r[0], "concept_name": r[1], "requirement": r[3]} for r in rows]
    out["growth_candidates"] = extraction.growth_candidates
    return out


def match(job_id, pool="ai", limit=50, offset=0):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT concept_id, concept_name, requirement FROM job_requirements
               WHERE job_id = %s AND concept_id IS NOT NULL""", (job_id,))
        return score_requirements(cur, cur.fetchall(), pool=pool, limit=limit, offset=offset)
    finally:
        conn.close()


def match_concepts(requirements, pool="all", limit=20, offset=0):
    """Deterministic, read-only scoring of explicit [{concept_id, requirement}] with the same code match() uses.
    Returns (result, unknown_concept_ids); no LLM, no writes."""
    conn = _conn()
    try:
        cur = conn.cursor()
        ids = [r["concept_id"] for r in requirements]
        cur.execute("SELECT concept_id, canonical_name FROM concepts WHERE status = 'ACTIVE' AND concept_id = ANY(%s)",
                    (ids,))
        names = dict(cur.fetchall())
        unknown = [c for c in dict.fromkeys(ids) if c not in names]
        if unknown:
            return None, unknown
        reqs = [(r["concept_id"], names[r["concept_id"]], r["requirement"]) for r in requirements]
        return score_requirements(cur, reqs, pool=pool, limit=limit, offset=offset), []
    finally:
        conn.close()


def score_requirements(cur, reqs, pool="ai", limit=50, offset=0):
    """The scoring behind match_job: reqs = [(concept_id, concept_name, requirement)]. Read-only."""
    if not reqs:
        return {"total": 0, "pool": 0, "items": []}
    concept_ids = [r[0] for r in reqs]
    pool_ids = _pool_ids(cur, pool)
    if not pool_ids:
        return {"total": 0, "pool": 0, "items": []}
    cur.execute(
        """SELECT talent_id, concept_id, status, usage_level, confidence
           FROM talent_evidence
           WHERE talent_id = ANY(%s) AND concept_id = ANY(%s)""",
        (pool_ids, concept_ids))
    LEVEL_RANK = {"CONTRIBUTOR_USAGE": 3, "ADVANCED_USAGE": 4,
                  "OBSERVED_USAGE": 2, "DECLARED": 1, "DECLARED_USAGE": 1}
    best = {}  # (talent, concept) -> (coverage, status, confidence, usage_level)
    for tid, cid, status, usage, conf in cur.fetchall():
        conf = float(conf) if conf is not None else None
        cov = _coverage(status, usage, conf)
        key = (tid, cid)
        cur_rank = LEVEL_RANK.get(usage or "", 0)
        if (key not in best or cov > best[key][0]
                or (cov == best[key][0] and cur_rank > LEVEL_RANK.get(best[key][3] or "", 0))):
            best[key] = (cov, status, conf, usage)
    # A requirement no talent in the pool has any evidence for can't separate anyone; it is
    # shown as "unscored" and left out of the denominator instead of capping every score.
    scorable = {cid for (_, cid), v in best.items() if v[0] > 0}
    denom = sum(REQ_WEIGHT[r[2]] for r in reqs if r[0] in scorable)
    results = []
    for tid in pool_ids:
        breakdown = []
        total = 0.0
        contrib = 0
        for cid, cname, reqtype in reqs:
            cov, status, conf, usage = best.get((tid, cid), (0.0, None, None, None))
            if cid not in scorable:
                breakdown.append({
                    "concept_id": cid, "concept_name": cname, "requirement": reqtype,
                    "coverage": 0.0, "state": "unscored", "evidence_status": None,
                    "confidence": None, "usage_level": None})
                continue
            total += REQ_WEIGHT[reqtype] * cov
            if usage in ("CONTRIBUTOR_USAGE", "ADVANCED_USAGE") and cov >= 0.8:
                contrib += 1
            breakdown.append({
                "concept_id": cid, "concept_name": cname, "requirement": reqtype,
                "coverage": round(cov, 2),
                "state": ("covered" if cov >= 0.8 else
                          "partial" if cov > 0 else "missing"),
                "evidence_status": status, "confidence": conf,
                "usage_level": usage})
        score = total / denom if denom else 0.0
        if score > 0:
            results.append({"talent_id": tid, "score": round(score, 3),
                            "contributor_concepts": contrib,
                            "breakdown": breakdown})
    # contributor-backed coverage wins ties (boost is display-invisible)
    results.sort(key=lambda r: (-r["score"], -r["contributor_concepts"]))
    return {"total": len(results), "pool": len(pool_ids),
            "items": results[offset:offset + limit]}
