"""Client-driven enrichment: the MCP client's own LLM judges raw evidence; we only serve it and store validated results.

No LLM and no network calls here, and no API keys. Reads data/tier1_github.sqlite (bio, repos), Neon talent_evidence
(existing concept assignments) and the ai_enrichment flag; writes the same two places scripts/e5_unified_ai_enrich.py
does: Neon talent_evidence rows (concept_id set, status INFERENCE, source 'client:...') and the ai_enrichment flag in
data/enrichment.sqlite, so match_job scoring and the viewer pick them up with no further step.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

from . import settings
from .enrichment import SCHEMA

USAGE_LEVELS = ("OBSERVED_USAGE", "CONTRIBUTOR_USAGE", "ADVANCED_USAGE", "DECLARED_USAGE", "DECLARED")
SOURCE_PREFIX = "client:"  # everything this module writes carries it; resubmits replace only these rows
MAX_REPOS = 25
MAX_TEXT = 300
PLACEHOLDER_SOURCES = ("none",)


def _clip(s, n=MAX_TEXT):
    s = " ".join(str(s).split()) if s else None
    return s if not s or len(s) <= n else s[: n - 1] + "…"


def _flagged():
    if not settings.ENRICHMENT.exists():
        return set()
    db = sqlite3.connect(f"file:{settings.ENRICHMENT}?mode=ro", uri=True)
    try:
        return {r[0] for r in db.execute("SELECT person_id FROM ai_enrichment WHERE ai_enriched = 1")}
    finally:
        db.close()


def _github(person_ids):
    """{person_id: (login, user dict, repos list)} for found accounts, read-only."""
    if not person_ids or not settings.TIER1_GITHUB.exists():
        return {}
    db = sqlite3.connect(f"file:{settings.TIER1_GITHUB}?mode=ro", uri=True)
    try:
        out = {}
        for i in range(0, len(person_ids), 900):
            chunk = person_ids[i:i + 900]
            for pid, login, status, uj, rj in db.execute(
                    "SELECT person_id, login, api_status, user_json, repos_json FROM github_raw WHERE api_status = 200"
                    f" AND person_id IN ({','.join('?' * len(chunk))})", chunk):
                try:
                    out[pid] = (login, json.loads(uj or "{}"), json.loads(rj or "[]"))
                except ValueError:
                    continue
        return out
    finally:
        db.close()


def _bundle(user, repos):
    repos = sorted((r for r in repos if isinstance(r, dict)),
                   key=lambda r: (r.get("fork") is True, -(r.get("stargazers_count") or 0), r.get("pushed_at") or ""))
    langs = {}
    for r in repos:
        if r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    return {
        "profile": {k: v for k, v in {
            "bio": _clip(user.get("bio"), 500), "company": _clip(user.get("company"), 100),
            "location": _clip(user.get("location"), 100), "website": _clip(user.get("blog"), 150),
            "followers": user.get("followers"), "public_repos": user.get("public_repos"),
        }.items() if v},
        "primary_languages": [k for k, _ in sorted(langs.items(), key=lambda kv: -kv[1])][:8],
        "repos": [{k: v for k, v in {
            "name": r.get("name"), "description": _clip(r.get("description"), 200), "language": r.get("language"),
            "topics": (r.get("topics") or [])[:8], "stars": r.get("stargazers_count") or None,
            "fork": True if r.get("fork") else None,
        }.items() if v not in (None, [], "")} for r in repos[:MAX_REPOS]],
        "repos_omitted": max(len(repos) - MAX_REPOS, 0),
        "readme": None,  # profile READMEs are not stored locally; the pipeline never keeps their text
    }


def _has_content(b):
    return bool(b["profile"].get("bio") or any(r.get("description") or r.get("topics") for r in b["repos"]))


def _existing(cur, ids):
    cur.execute(
        """SELECT talent_id, concept_id, concept_name, status, usage_level, confidence, source FROM talent_evidence
           WHERE talent_id = ANY(%s) AND concept_id IS NOT NULL AND source <> ALL(%s) ORDER BY confidence DESC""",
        (ids, list(PLACEHOLDER_SOURCES)))
    out = {}
    for tid, cid, name, status, usage, conf, src in cur.fetchall():
        out.setdefault(tid, []).append({"concept_id": cid, "concept_name": name, "status": status,
                                        "usage_level": usage, "confidence": float(conf), "source": src})
    return out


def batch(con, limit=10, only_unenriched=True):
    """Talents (P1 first, most active first) with a non-empty evidence bundle. `con` = DuckDB connection."""
    import psycopg2
    flagged = _flagged() if only_unenriched else set()
    out, offset, page = [], 0, 400
    conn = psycopg2.connect(settings.NEON_URL, connect_timeout=8)
    try:
        cur = conn.cursor()
        while len(out) < limit:
            rows = con.execute(
                "SELECT person_id, display_name, github_login FROM talent_seed WHERE priority_cohort IN ('P1','P2','P3')"
                " AND NOT coalesce(flag_probable_bot, false) AND github_login IS NOT NULL"
                " ORDER BY priority_cohort, active_days_in_window DESC NULLS LAST, person_id LIMIT ? OFFSET ?",
                [page, offset]).fetchall()
            if not rows:
                break
            offset += page
            rows = [r for r in rows if r[0] not in flagged]
            gh = _github([r[0] for r in rows])
            cand = [(r, _bundle(gh[r[0]][1], gh[r[0]][2])) for r in rows if r[0] in gh]
            cand = [(r, b) for r, b in cand if _has_content(b)][: limit - len(out)]
            ex = _existing(cur, [r[0] for r, _ in cand]) if cand else {}
            for (pid, name, login), b in cand:
                out.append({"talent_id": pid, "display_name": name, "github_username": gh[pid][0] or login,
                            "evidence_bundle": {**b, "existing_concepts": ex.get(pid, [])}})
    finally:
        conn.close()
    return out


def submit(talent_id, concepts, source_note=None):
    """Validate against the ontology, replace this talent's client rows, set the flag. Returns the result dict;
    raises ValueError with a user-facing message on bad input (nothing is written then)."""
    import psycopg2
    ids = [c["concept_id"] for c in concepts]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"Duplicate concept_ids: {', '.join(dup)}. List each concept once.")
    note = re.sub(r"[^\w .:/@+-]", "", source_note or "mcp-client")[:60].strip() or "mcp-client"
    source = SOURCE_PREFIX + note
    conn = psycopg2.connect(settings.NEON_URL, connect_timeout=8)
    try:
        cur = conn.cursor()
        cur.execute("SELECT concept_id, canonical_name, concept_type FROM concepts WHERE status = 'ACTIVE'"
                    " AND concept_id = ANY(%s)", (ids,))
        known = {r[0]: r[1:] for r in cur.fetchall()}
        unknown = [i for i in dict.fromkeys(ids) if i not in known]
        if unknown:
            raise ValueError(f"Unknown concept_id(s): {', '.join(unknown)}. Use ids from list_concepts; nothing was stored.")
        stored = []
        # one transaction: replace this talent's earlier client rows only (never github:/components:/llm:/derived: rows)
        cur.execute("DELETE FROM talent_evidence WHERE talent_id = %s AND source LIKE %s", (talent_id, SOURCE_PREFIX + "%"))
        for c in concepts:
            name, ctype = known[c["concept_id"]]
            eid = f"ev_client_{talent_id}_{c['concept_id']}".replace(":", "_")
            cur.execute(
                """INSERT INTO talent_evidence (evidence_id, talent_id, concept_id, concept_name, concept_type, status,
                       usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,%s,%s,'INFERENCE',%s,%s,%s,%s,now())""",
                (eid, talent_id, c["concept_id"], name, ctype, c["usage_level"], c["confidence"], source,
                 _clip(c["evidence"], 500)))
            stored.append({"concept_id": c["concept_id"], "concept_name": name, "concept_type": ctype,
                           "usage_level": c["usage_level"], "confidence": c["confidence"], "status": "INFERENCE"})
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db = sqlite3.connect(settings.ENRICHMENT)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)
        db.execute("INSERT OR REPLACE INTO ai_enrichment VALUES (?, 1, ?, ?)", (talent_id, now, source))
        db.commit()
    finally:
        db.close()
    return {"talent_id": talent_id, "stored": len(stored), "source": source, "concepts": stored}
