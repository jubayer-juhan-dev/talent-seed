"""AI enrichment (Neon) reads for the viewer.

Talent evidence and LLM summaries live in Postgres (Neon); this module fetches
them per person for the profile UI. Returns None when Neon is not configured.
"""
import psycopg2

from . import settings


def fetch(person_id):
    """Enrichment payload for one person, or None when Neon is unavailable."""
    if not settings.NEON_URL:
        return None
    try:
        conn = psycopg2.connect(settings.NEON_URL, connect_timeout=8)
    except Exception:
        return None
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT summary, seniority_band, seniority_confidence, llm_model,
                      location_text, location_confidence, location
               FROM talent_profiles WHERE talent_id = %s""",
            (person_id,),
        )
        prof = cur.fetchone()
        cur.execute(
            """SELECT concept_name, concept_type, status, usage_level,
                      confidence, source, note
               FROM talent_evidence WHERE talent_id = %s
               ORDER BY confidence DESC""",
            (person_id,),
        )
        evidence = [
            {
                "concept_name": r[0],
                "concept_type": r[1],
                "status": r[2],
                "usage_level": r[3],
                "confidence": float(r[4]),
                "source": r[5],
                "note": r[6],
            }
            for r in cur.fetchall()
        ]
    except Exception:
        return None
    finally:
        conn.close()
    if not prof and not evidence:
        return {"enriched": False, "evidence": []}
    return {
        "enriched": True,
        "summary": prof[0] if prof else None,
        "seniority_band": prof[1] if prof else None,
        "seniority_confidence": float(prof[2]) if prof and prof[2] is not None else None,
        "llm_model": prof[3] if prof else None,
        "location_text": prof[4] if prof else None,
        "location_confidence": float(prof[5]) if prof and prof[5] is not None else None,
        "location": prof[6] if prof else None,
        "evidence": evidence,
    }

def lookup_locations(person_ids):
    """{person_id: resolved location} for the given ids (GitHub > AI)."""
    ids = [i for i in person_ids if i]
    if not ids:
        return {}
    try:
        conn = psycopg2.connect(settings.NEON_URL, connect_timeout=8)
    except Exception:
        return {}
    try:
        cur = conn.cursor()
        out = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            cur.execute(
                "SELECT talent_id, location FROM talent_profiles "
                "WHERE talent_id = ANY(%s) AND location IS NOT NULL",
                (chunk,))
            out.update({r[0]: r[1] for r in cur.fetchall()})
        return out
    except Exception:
        return {}
    finally:
        conn.close()


def add_locations(rows):
    """Fill row['location'] with the resolved location when present, in place."""
    found = lookup_locations(r["person_id"] for r in rows)
    for r in rows:
        if found.get(r["person_id"]):
            r["location"] = found[r["person_id"]]
    return rows

