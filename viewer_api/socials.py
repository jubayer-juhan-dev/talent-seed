"""Social profiles (LinkedIn / X / Telegram) found for prospects.

Kept in data/enrichment.sqlite beside the AI-enrichment flag: talent_seed.duckdb is rebuilt from
scratch, so finds must live in the sidecar file. Two writers: deterministic extraction from the
tier-1 GitHub cache (social_accounts, twitter_username, bio/blog links) and client submissions
through the MCP (a client AI that spotted a handle in a bio it read). First writer wins per
field — a stored value is never silently overwritten.
"""

import json
import re
import sqlite3
from datetime import datetime, timezone

from .settings import ENRICHMENT, TIER1_GITHUB

SCHEMA = """
CREATE TABLE IF NOT EXISTS talent_socials (
    person_id    TEXT PRIMARY KEY,
    linkedin_url TEXT,
    x_handle     TEXT,
    telegram     TEXT,
    source       TEXT,
    found_by     TEXT,
    updated_at   TEXT NOT NULL
);
"""

FIELDS = ("linkedin_url", "x_handle", "telegram")

_LI_RE = re.compile(r"linkedin\.com/(?:in|company)/[\w\-%.]+", re.I)
_X_RE = re.compile(r"(?:twitter\.com|x\.com)/@?([A-Za-z0-9_]{1,15})", re.I)
_TG_RE = re.compile(r"(?:t\.me|telegram\.me|telegram\.org)/([A-Za-z0-9_]{5,})", re.I)
_TG_RESERVED = {"joinchat", "share", "s", "addstickers", "proxy"}


def _clean_x(v):
    if not v:
        return None
    v = str(v).strip()
    m = _X_RE.search(v)
    if m:
        v = m.group(1)
    v = v.lstrip("@").strip()
    return ("@" + v) if re.fullmatch(r"[A-Za-z0-9_]{1,15}", v) else None


def _clean_linkedin(v):
    if not v:
        return None
    m = _LI_RE.search(str(v).strip())
    return ("https://" + m.group(0)) if m else None


def _clean_telegram(v):
    if not v:
        return None
    v = str(v).strip()
    m = _TG_RE.search(v)
    if m:
        v = m.group(1)
    v = v.lstrip("@").strip()
    if v.lower() in _TG_RESERVED:
        return None
    return ("@" + v) if re.fullmatch(r"[A-Za-z0-9_]{5,32}", v) else None


CLEANERS = {"linkedin_url": _clean_linkedin, "x_handle": _clean_x, "telegram": _clean_telegram}


def normalise(fields: dict) -> dict:
    out = {}
    for f in FIELDS:
        c = CLEANERS[f](fields.get(f))
        if c:
            out[f] = c
    return out


def extract(person_id: str) -> dict:
    """Deterministic finds from the tier-1 GitHub cache: social_accounts, twitter_username, bio/blog links."""
    if not TIER1_GITHUB.exists():
        return {}
    db = sqlite3.connect(f"file:{TIER1_GITHUB}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT api_status, user_json FROM github_raw WHERE person_id = ?", (person_id,)
        ).fetchone()
    finally:
        db.close()
    if not row or row[0] == 404:
        return {}
    try:
        u = json.loads(row[1] or "{}")
    except (TypeError, ValueError):
        return {}
    accounts = u.get("social_accounts") or []
    social_urls = [a.get("url") or "" for a in accounts]
    text = " ".join([u.get("bio") or "", u.get("blog") or "", *social_urls])
    found = {}
    li = next((a.get("url") for a in accounts if a.get("provider") == "linkedin"), None)
    if li:
        found["linkedin_url"] = li
    if u.get("twitter_username"):
        found["x_handle"] = "@" + str(u["twitter_username"]).lstrip("@")
    m = _TG_RE.search(text)
    if m and m.group(1).lower() not in _TG_RESERVED:
        found["telegram"] = "@" + m.group(1)
    if "linkedin_url" not in found:
        m = _LI_RE.search(text)
        if m:
            found["linkedin_url"] = "https://" + m.group(0)
    if "x_handle" not in found:
        m = _X_RE.search(text)
        if m:
            found["x_handle"] = "@" + m.group(1)
    return normalise(found)


def _connect():
    db = sqlite3.connect(ENRICHMENT)
    db.execute(SCHEMA)
    return db


def lookup(person_ids):
    """{person_id: {linkedin_url, x_handle, telegram, source, found_by}} for ids with stored socials."""
    ids = [p for p in dict.fromkeys(person_ids) if p]
    if not ids or not ENRICHMENT.exists():
        return {}
    db = sqlite3.connect(f"file:{ENRICHMENT}?mode=ro", uri=True)
    try:
        out = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i:i + 900]
            for pid, li, x, tg, src, by in db.execute(
                f"SELECT person_id, linkedin_url, x_handle, telegram, source, found_by FROM talent_socials "
                f"WHERE person_id IN ({','.join('?' * len(chunk))})",
                chunk,
            ):
                out[pid] = {"linkedin_url": li, "x_handle": x, "telegram": tg, "source": src, "found_by": by}
        return out
    except sqlite3.OperationalError:  # table not created yet
        return {}
    finally:
        db.close()


def store(person_id: str, fields: dict, source: str, found_by: str | None) -> dict:
    """Fill empty fields only (first writer wins). Returns the stored row and what this call added."""
    clean = normalise(fields)
    now = datetime.now(timezone.utc).isoformat()
    db = _connect()
    try:
        row = db.execute(
            "SELECT linkedin_url, x_handle, telegram FROM talent_socials WHERE person_id = ?", (person_id,)
        ).fetchone()
        cur = dict(zip(FIELDS, row)) if row else {f: None for f in FIELDS}
        added = {}
        for f, v in clean.items():
            if not cur.get(f):
                cur[f] = v
                added[f] = v
        db.execute(
            "INSERT INTO talent_socials (person_id, linkedin_url, x_handle, telegram, source, found_by, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(person_id) DO UPDATE SET "
            "linkedin_url=excluded.linkedin_url, x_handle=excluded.x_handle, telegram=excluded.telegram, "
            "source=excluded.source, found_by=excluded.found_by, updated_at=excluded.updated_at",
            (person_id, cur["linkedin_url"], cur["x_handle"], cur["telegram"], source, found_by, now),
        )
        db.commit()
        return {"stored": cur, "added": added}
    finally:
        db.close()
