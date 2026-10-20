"""AI enrichment flag, kept in data/enrichment.sqlite beside the generated database.

talent_seed.duckdb is rebuilt from scratch, so per-person state that must survive rebuilds lives in this
separate file. scripts/set_ai_enriched.py writes it; the API only reads it. Nobody is AI-enriched until
something marks them, so a missing file or row means ai_enriched = false.
"""

import sqlite3

import duckdb

from .settings import DUCKDB_EXTENSIONS, ENRICHMENT

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_enrichment (
    person_id    TEXT PRIMARY KEY,
    ai_enriched  INTEGER NOT NULL CHECK (ai_enriched IN (0, 1)),
    enriched_at  TEXT NOT NULL,   -- ISO timestamp, UTC
    enriched_by  TEXT             -- model or process that did the enrichment
);
"""


def lookup(person_ids):
    """{person_id: (enriched_at, enriched_by)} for the given ids that are AI-enriched."""
    if not person_ids or not ENRICHMENT.exists():
        return {}
    db = sqlite3.connect(f"file:{ENRICHMENT}?mode=ro", uri=True)
    try:
        out = {}
        ids = list(person_ids)
        for i in range(0, len(ids), 900):  # SQLite parameter limit
            chunk = ids[i:i + 900]
            out.update({pid: (at, by) for pid, at, by in db.execute(
                f"SELECT person_id, enriched_at, enriched_by FROM ai_enrichment "
                f"WHERE ai_enriched = 1 AND person_id IN ({','.join('?' * len(chunk))})", chunk)})
        return out
    finally:
        db.close()


def add_ai_enriched(rows):
    """Set ai_enriched (and when/by whom, if enriched) on each row, in place."""
    found = lookup(r["person_id"] for r in rows)
    for r in rows:
        hit = found.get(r["person_id"])
        r["ai_enriched"] = hit is not None
        if hit:
            r["ai_enriched_at"], r["ai_enriched_by"] = hit
    return rows


def attach(con):
    """Make the flag queryable from DuckDB as enr.ai_enrichment (only needed for the filter)."""
    if not ENRICHMENT.exists():
        return False
    con.execute(f"SET home_directory = '{DUCKDB_EXTENSIONS.parent}'")
    con.execute(f"SET extension_directory = '{DUCKDB_EXTENSIONS}'")
    try:
        con.execute("LOAD sqlite")
    except duckdb.Error:  # first use: download the extension once into data/duckdb_extensions
        con.execute("INSTALL sqlite")
        con.execute("LOAD sqlite")
    try:
        con.execute(f"ATTACH '{ENRICHMENT}' AS enr (TYPE sqlite, READ_ONLY)")
    except duckdb.Error:
        pass  # already attached on this connection
    return True
