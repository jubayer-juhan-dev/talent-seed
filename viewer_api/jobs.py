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
        cur.execute(
            """SELECT j.job_id, j.title, j.company, j.location_text, j.location_country,
                      j.source, j.posted_at,
                      (SELECT COUNT(*) FROM job_requirements r WHERE r.job_id = j.job_id)
               FROM jobs j WHERE j.active ORDER BY j.fetched_at DESC""")
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) | {"posted_at": str(row[6])[:10] if row[6] else None}
                for row in cur.fetchall()]
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


def match(job_id, pool="ai", limit=50):
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT concept_id, concept_name, requirement FROM job_requirements
               WHERE job_id = %s AND concept_id IS NOT NULL""", (job_id,))
        reqs = cur.fetchall()
        if not reqs:
            return []
        concept_ids = [r[0] for r in reqs]
        pool_ids = _pool_ids(cur, pool)
        if not pool_ids:
            return []
        cur.execute(
            """SELECT talent_id, concept_id, status, usage_level, confidence
               FROM talent_evidence
               WHERE talent_id = ANY(%s) AND concept_id = ANY(%s)""",
            (pool_ids, concept_ids))
        best = {}  # (talent, concept) -> (coverage, status, confidence)
        for tid, cid, status, usage, conf in cur.fetchall():
            conf = float(conf) if conf is not None else None
            cov = _coverage(status, usage, conf)
            key = (tid, cid)
            if key not in best or cov > best[key][0]:
                best[key] = (cov, status, conf)
        denom = sum(REQ_WEIGHT[r[2]] for r in reqs)
        results = []
        for tid in pool_ids:
            breakdown = []
            total = 0.0
            for cid, cname, reqtype in reqs:
                cov, status, conf = best.get((tid, cid), (0.0, None, None))
                total += REQ_WEIGHT[reqtype] * cov
                breakdown.append({
                    "concept_id": cid, "concept_name": cname, "requirement": reqtype,
                    "coverage": round(cov, 2),
                    "state": ("covered" if cov >= 1.0 else
                              "partial" if cov > 0 else "missing"),
                    "evidence_status": status, "confidence": conf})
            score = total / denom if denom else 0.0
            if score > 0:
                results.append({"talent_id": tid, "score": round(score, 3),
                                "breakdown": breakdown})
        results.sort(key=lambda r: -r["score"])
        return results[:limit]
    finally:
        conn.close()
