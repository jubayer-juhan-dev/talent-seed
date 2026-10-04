"""GitHub logins found later by scripts/m5_lookup_github_logins.py, overlaid where talent_seed has none.

The lookup writes data/github_logins.sqlite (WAL), so this reads it read-only while a lookup may be running.
"""

import sqlite3

from .settings import LOGINS


def looked_up(where_sql, params):
    """Rows from the login-lookup file (empty if the file doesn't exist yet). Read-only."""
    if not LOGINS.exists():
        return []
    db = sqlite3.connect(f"file:{LOGINS}?mode=ro", uri=True)
    try:
        return db.execute(f"SELECT person_id, github_login, github_user_id, method, looked_up_at FROM github_logins "
                          f"WHERE github_login IS NOT NULL AND {where_sql}", params).fetchall()
    finally:
        db.close()


def add_logins(rows):
    """Fill github_login (and github_url / github_user_id when present) from the lookup file, in place.
    COMMIT_API matches are MEDIUM confidence, as in inspect_developer.py."""
    need = [r["person_id"] for r in rows if not r.get("github_login")]
    found = {}
    for i in range(0, len(need), 900):  # SQLite parameter limit
        chunk = need[i:i + 900]
        found.update({pid: x for pid, *x in looked_up(f"person_id IN ({','.join('?' * len(chunk))})", chunk)})
    for r in rows:
        hit = found.get(r["person_id"])
        if not hit:
            continue
        login, uid, method, at = hit
        r["github_login"] = login
        r["github_login_source"] = "GITHUB_API_" + method
        r["github_login_looked_up_at"] = at
        if "github_url" in r:
            r["github_url"] = f"https://github.com/{login}"
        if "github_user_id" in r and r["github_user_id"] is None:
            r["github_user_id"] = uid
        if "github_confidence" in r and method == "COMMIT_API" and r["github_confidence"] in (None, "NONE", "LOW"):
            r["github_confidence"] = "MEDIUM"
    return rows
