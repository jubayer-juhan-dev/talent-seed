"""Job Graph (ProspectMind): jobs, requirements, and j3 matching.

Matching is deterministic math over Neon tables — no LLM at query time.
Score per spec v0.4 proximity: S_d = sum(a_t * m(t,E)) / sum(a_t), with
a_t = 1.0 (required) / 0.4 (nice_to_have) and m from the talent's best
evidence for concept t: FACT observed+ = 1.0, FACT declared = 0.7,
INFERENCE = its confidence, missing = 0.
"""
from __future__ import annotations

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


def match(job_id, pool="ai", limit=50, offset=0):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT concept_id, concept_name, requirement FROM job_requirements
               WHERE job_id = %s AND concept_id IS NOT NULL""", (job_id,))
        reqs = cur.fetchall()
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
    finally:
        conn.close()
