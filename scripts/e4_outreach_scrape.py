#!/usr/bin/env python3
"""e4 — outreach scrape (rules-based, free, no AI).

For talents missing X and/or LinkedIn on their GitHub profile:
  1. Scrape their `blog` website for twitter.com/x.com + linkedin.com links
  2. Fetch their profile README (github.com/<login>/<login>) for social badges
  3. Scan top-5 repos by stars (homepage + description) for social links
  4. GO INSIDE every found social URL and extract contact info
     (emails in bios, linked websites) — Juhan's rule 2026-10-20.

Reads the SQLite cache (read-only). No GitHub API calls. Resumable via JSONL.
Code only — DO NOT RUN without Juhan's go-ahead.

Usage:
    python scripts/e4_outreach_scrape.py [--limit N]
"""
import argparse
import html
import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQLITE = ROOT / "data" / "tier1_github.sqlite"
OUT = ROOT / "out" / "enrichment" / "outreach_candidates.jsonl"

TIMEOUT = 10  # seconds per fetch, fail soft
UA = {"User-Agent": "Mozilla/5.0 (compatible; ProspectMindBot/1.0; +https://goodhive.io)"}

SOCIAL_PATTERNS = {
    "x": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/in/([A-Za-z0-9\-_%]{3,100})", re.I),
}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TAG_RE = re.compile(r"<[^>]+>")


def fetch(url):
    """Fetch a URL, return text or None. Fail soft, 10s timeout."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ctype = r.headers.get("Content-Type", "")
            if "text" not in ctype and "html" not in ctype:
                return None
            return r.read(500_000).decode("utf-8", errors="ignore")
    except Exception:
        return None


def find_socials(text):
    """Extract {channel: url} from text."""
    found = {}
    for channel, pat in SOCIAL_PATTERNS.items():
        m = pat.search(text or "")
        if m and channel not in found:
            # keep the full matched URL, not just the handle
            found[channel] = m.group(0).split("?")[0].rstrip("/")
    return found


def extract_contacts(page_text, url):
    """Pull contact info from inside a social profile page."""
    if not page_text:
        return {}
    # strip tags, unescape, keep it short
    text = html.unescape(TAG_RE.sub(" ", page_text))
    text = re.sub(r"\s+", " ", text)[:2000]
    emails = sorted(set(EMAIL_RE.findall(text)))
    # drop obvious non-personal emails
    emails = [e for e in emails if not e.lower().endswith((".png", ".jpg", ".gif"))]
    websites = sorted(set(re.findall(r"https?://[^\s\"'<>]+", text)))[:5]
    return {"emails": emails[:5], "websites": websites, "snippet": text[:500]}


def has_channel(user, channel):
    """Does the GitHub profile already list this channel? (mirrors tier1.py rules)"""
    if channel == "x":
        return bool(user.get("twitter_username"))
    if channel == "linkedin":
        for sa in user.get("social_accounts") or []:
            if str(sa.get("provider", "")).lower() == "linkedin":
                return True
        blog = (user.get("blog") or "").lower()
        return "linkedin.com/" in blog
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max people (0 = all)")
    ap.add_argument("--output", default=str(OUT))
    args = ap.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # resumable: skip person_ids already written
    done = set()
    if out_path.exists():
        with open(out_path) as f:
            for line in f:
                try:
                    done.add(json.loads(line)["person_id"])
                except Exception:
                    pass
    print(f"resuming: {len(done)} already done", flush=True)

    con = sqlite3.connect(f"file:{SQLITE}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT person_id, login, user_json, repos_json FROM github_raw WHERE api_status = 200"
    ).fetchall()
    print(f"{len(rows)} people with GitHub data", flush=True)

    n_done = n_found = 0
    out_f = open(out_path, "a")
    try:
        for person_id, login, user_json, repos_json in rows:
            if person_id in done:
                continue
            if args.limit and n_done >= args.limit:
                break
            try:
                user = json.loads(user_json or "{}")
            except Exception:
                continue
            repos = []
            try:
                repos = json.loads(repos_json or "[]")
            except Exception:
                pass

            missing = [c for c in ("x", "linkedin") if not has_channel(user, c)]
            channels = {}  # channel -> {url, source}

            if missing:
                # 1. blog / website
                blog = (user.get("blog") or "").strip()
                if blog:
                    if not blog.startswith("http"):
                        blog = "https://" + blog
                    page = fetch(blog)
                    for ch, url in find_socials(page or "").items():
                        if ch in missing and ch not in channels:
                            channels[ch] = {"url": url, "source": "own_website"}
                # 2. profile README
                readme = fetch(
                    f"https://raw.githubusercontent.com/{login}/{login}/HEAD/README.md"
                )
                for ch, url in find_socials(readme or "").items():
                    if ch in missing and ch not in channels:
                        channels[ch] = {"url": url, "source": "profile_readme"}
                # 3. top-5 repos by stars: homepage + description
                top = sorted(repos, key=lambda r: r.get("stargazers_count", 0) or 0,
                             reverse=True)[:5]
                for r in top:
                    hay = f"{r.get('homepage') or ''} {r.get('description') or ''}"
                    for ch, url in find_socials(hay).items():
                        if ch in missing and ch not in channels:
                            channels[ch] = {"url": url, "source": "repo_readme"}

            # 4. go inside every found profile and extract contact info
            result_channels = []
            for ch, info in channels.items():
                contacts = extract_contacts(fetch(info["url"]), info["url"])
                if contacts.get("emails") or contacts.get("websites"):
                    n_found += 1
                result_channels.append({
                    "channel": ch,
                    "url": info["url"],
                    "source": info["source"],
                    "contact_info": contacts,
                })

            out_f.write(json.dumps({
                "person_id": person_id,
                "login": login,
                "missing": missing,
                "channels": result_channels,
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }) + "\n")
            out_f.flush()
            n_done += 1
            if n_done % 100 == 0:
                print(f"  {n_done} scraped, {n_found} with contact info", flush=True)
    finally:
        out_f.close()
        con.close()

    print(f"DONE: {n_done} scraped this run, {n_found} channels with contact info found")
    print(f"output: {out_path}")


if __name__ == "__main__":
    main()
