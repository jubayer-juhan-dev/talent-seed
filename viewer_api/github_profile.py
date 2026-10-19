"""GitHub profile details for the viewer's Contact tab.

Reads data/tier1_github.sqlite (table github_raw) read-only — the file is
written while the harvest runs (WAL mode), so this uses the same read-only
pattern as viewer_api/logins.py.

Missing keys mean "not fetched yet", not "none". A 404 api_status means the
GitHub account was deleted.
"""
import json
import sqlite3

from .settings import TIER1_GITHUB


def _linkedin(user):
    """LinkedIn URL: social_accounts provider 'linkedin', else blog pointing at linkedin.com."""
    li = next(
        (a.get("url") for a in user.get("social_accounts") or [] if a.get("provider") == "linkedin"),
        None,
    )
    if not li and "linkedin.com/" in (user.get("blog") or "").lower():
        li = user["blog"]
    return li


def fetch(person_id):
    """GitHub profile details for one person, or None when not fetched yet."""
    if not TIER1_GITHUB.exists():
        return None
    db = sqlite3.connect(f"file:{TIER1_GITHUB}?mode=ro", uri=True)
    try:
        row = db.execute(
            "SELECT api_status, user_json FROM github_raw WHERE person_id = ?", (person_id,)
        ).fetchone()
    finally:
        db.close()
    if not row:
        return None
    status, user_json = row
    if status == 404:
        return {"deleted": True}
    try:
        u = json.loads(user_json or "{}")
    except (TypeError, ValueError):
        return None
    blog = (u.get("blog") or "").strip()
    twitter = (u.get("twitter_username") or "").strip()
    return {
        "deleted": False,
        "login": u.get("login"),
        "name": u.get("name"),
        "bio": u.get("bio"),
        "company": u.get("company"),
        "location": u.get("location"),
        "website": blog or None,
        "x_handle": ("@" + twitter.lstrip("@")) if twitter else None,
        "x_url": f"https://x.com/{twitter.lstrip('@')}" if twitter else None,
        "linkedin_url": _linkedin(u),
        "public_email": u.get("email") or None,
        "hireable": u.get("hireable"),
        "followers": u.get("followers"),
        "public_repos": u.get("public_repos"),
        "account_created": (u.get("created_at") or "")[:10] or None,
    }
