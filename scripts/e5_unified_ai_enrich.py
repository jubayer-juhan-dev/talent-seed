#!/usr/bin/env python3
"""e5 — unified AI enrichment: one Luna call per person.

Returns roles + seniority + summary + outreach channels (X / LinkedIn / email)
in a single structured output. Supersedes e3 for the full run.

New vs e3:
  - outreach[] in the output schema, fed by e4 scrape snippets + Serper web search
  - --triage: skip people whose rules evidence is already rich (>=10 strong FACTs)
  - outreach rows -> talent_evidence as FACT (github_profile / own_website basis)
    or INFERENCE (web-search basis), never below 0.6 without review flag

Code only — DO NOT RUN without Juhan's go-ahead (standing rule: no AI
enrichment without his explicit permission).

Usage:
    python scripts/e5_unified_ai_enrich.py [--limit 20] [--model gpt-6-luna] [--triage]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
IN_JSON = ROOT / "out" / "enrichment" / "p1_tier1_enriched.json"
E4_JSONL = ROOT / "out" / "enrichment" / "outreach_candidates.jsonl"

AI_FLAG_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_enrichment (
    person_id    TEXT PRIMARY KEY,
    ai_enriched  INTEGER NOT NULL CHECK (ai_enriched IN (0, 1)),
    enriched_at  TEXT NOT NULL,
    enriched_by  TEXT
);
"""

ENRICHMENT_SQLITE = ROOT / "data" / "enrichment.sqlite"


def flag_ai_enriched(talent_id, by):
    """Mark someone AI-enriched so the viewer shows the AI section immediately."""
    import sqlite3
    from datetime import datetime, timezone
    db = sqlite3.connect(ENRICHMENT_SQLITE)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(AI_FLAG_SCHEMA)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.execute("INSERT OR REPLACE INTO ai_enrichment VALUES (?, 1, ?, ?)",
               (talent_id, now, by))
    db.commit()
    db.close()


def ensure_db():
    """Reconnect to Neon if the connection dropped (it closes idle conns)."""
    global conn, cur
    try:
        cur.execute("SELECT 1")
    except Exception:
        import psycopg2
        conn = psycopg2.connect(db_url())
        conn.autocommit = True
        cur = conn.cursor()


PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS talent_profiles (
  talent_id            TEXT PRIMARY KEY,
  summary              TEXT,
  seniority_band       TEXT CHECK (seniority_band IN
                         ('junior','mid','senior','staff','unknown')),
  seniority_confidence NUMERIC(3,2),
  llm_model            TEXT NOT NULL,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

TRIAGE_FACT_THRESHOLD = 10  # >= this many strong FACTs -> skip Luna


class RoleInference(BaseModel):
    concept_id: str = Field(description="Ontology role concept id, e.g. PM.ROLE.0003")
    confidence: float = Field(ge=0, le=1)
    reasoning: str = Field(description="One sentence, grounded in the profile data")


class Seniority(BaseModel):
    band: str = Field(description="junior | mid | senior | staff | unknown")
    confidence: float = Field(ge=0, le=1)
    reasoning: str


class OutreachChannel(BaseModel):
    channel: str = Field(description="x | linkedin | email")
    url: str = Field(description="Profile URL, or mailto: for email")
    confidence: float = Field(ge=0, le=1)
    match_basis: str = Field(
        description="github_profile | own_website | login_match | "
                    "name_bio_match | name_only")
    reasoning: str = Field(description="Why you believe this belongs to this person")


class Location(BaseModel):
    city: str = Field(default="", description="City if found, else empty")
    country: str = Field(default="", description="Country if found, else empty")
    confidence: float = Field(default=0.0, ge=0, le=1)
    basis: str = Field(default="",
                       description="web_profile | bio_match | none")


class EnrichmentOutput(BaseModel):
    roles: list[RoleInference] = Field(
        description="Inferred roles, strongest first. Empty if no confident inference.")
    seniority: Seniority
    summary: str = Field(description="2-3 line recruiter-readable summary")
    outreach: list[OutreachChannel] = Field(
        description="X / LinkedIn / email channels. Empty if none found with "
                    "confidence >= 0.4. Never invent a URL.")
    location: Location = Field(
        default_factory=Location,
        description="Where this person is based, from web search. "
                    "Empty if nothing found. Never guess from the name.")


def db_url():
    u = os.environ.get("DATABASE_URL")
    if not u:
        for line in open(ROOT / ".env"):
            if line.startswith("DATABASE_URL="):
                u = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not u:
        sys.exit("no DATABASE_URL in env or .env")
    return u


def fmt_counted(d, n=10):
    if not d:
        return "—"
    if isinstance(d, dict):
        items = sorted(d.items(), key=lambda kv: -kv[1])[:n]
        return ", ".join(f"{k} ({v})" for k, v in items)
    return ", ".join(str(x) for x in d[:n])


def get_top_repos(person_id, n=10):
    import sqlite3
    try:
        c = sqlite3.connect(f"file:{ROOT / 'data' / 'tier1_github.sqlite'}?mode=ro",
                            uri=True)
        row = c.execute(
            "SELECT repos_json FROM github_raw WHERE person_id = ?", (person_id,)
        ).fetchone()
        c.close()
        if not row or not row[0]:
            return []
        repos = json.loads(row[0])
        repos.sort(key=lambda r: r.get("stargazers_count", 0) or 0, reverse=True)
        return repos[:n]
    except Exception:
        return []


def get_contribution_repos(person_id, n=15):
    import duckdb
    try:
        c = duckdb.connect(str(ROOT / "data" / "talent_seed.duckdb"), read_only=True)
        rows = c.execute(
            """SELECT repo_name, commits, active_days FROM talent_seed_repos
               WHERE person_id = ? AND NOT inherited_history
               ORDER BY commits DESC LIMIT ?""",
            (person_id, n),
        ).fetchall()
        c.close()
        return rows
    except Exception:
        return []


def load_e4():
    """e4 outreach candidates keyed by person_id."""
    out = {}
    if not E4_JSONL.exists():
        return out
    with open(E4_JSONL) as f:
        for line in f:
            try:
                r = json.loads(line)
                out[r["person_id"]] = r
            except Exception:
                pass
    return out


def triage_score(person):
    """Count of strong (>=0.7) FACT rows. Rich profiles don't need Luna."""
    return sum(1 for e in person.get("evidence", [])
               if e.get("status") == "FACT" and (e.get("confidence") or 0) >= 0.7)


WALLED = ("linkedin.com", "twitter.com", "x.com", "facebook.com", "instagram.com")
_X_RE = None
_LI_RE = None
_EM_RE = None


def _patterns():
    global _X_RE, _LI_RE, _EM_RE
    import re
    if _X_RE is None:
        _X_RE = re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([A-Za-z0-9_]{1,15})", re.I)
        _LI_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([A-Za-z0-9\-_%]{3,100})", re.I)
        _EM_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
    return _X_RE, _LI_RE, _EM_RE


def fetch_page_extract(url, max_chars=2500):
    """Fetch a page free; return visible text + any X/LinkedIn/email links found.
    Login-walled domains are skipped (they return a wall, not content)."""
    import re, urllib.request
    if any(w in url for w in WALLED):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read(400_000).decode("utf-8", "ignore")
    except Exception:
        return ""
    x_re, li_re, em_re = _patterns()
    found = []
    for pat, label in ((x_re, "X"), (li_re, "LinkedIn")):
        for m in pat.finditer(html):
            u = m.group(0)
            if u not in found:
                found.append(u)
    emails = sorted({e for e in em_re.findall(html)
                     if not e.endswith((".png", ".jpg", ".gif", ".svg"))})
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:max_chars]
    out = []
    if found:
        out.append("social links on page: " + ", ".join(found[:6]))
    if emails:
        out.append("emails on page: " + ", ".join(emails[:4]))
    if text:
        out.append("page text: " + text)
    return chr(10).join(out)


def serper_search_rich(query, num=8, fetch_top=3):
    """Serper snippets + full content of the top non-walled result pages."""
    import json as _json, os, urllib.request
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        return ""
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=_json.dumps({"q": query, "num": num}).encode(),
            headers={"X-API-KEY": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = _json.loads(r.read())
    except Exception:
        return ""
    organic = (data.get("organic") or [])[:num]
    lines = []
    for it in organic:
        lines.append(f"- {it.get('title','')} | {it.get('link','')} | {(it.get('snippet') or '')[:200]}")
    from concurrent.futures import ThreadPoolExecutor
    targets = [it.get("link") or "" for it in organic]
    targets = [u for u in targets if u and not any(w in u for w in WALLED)][:fetch_top]
    with ThreadPoolExecutor(max_workers=fetch_top) as ex:
        for link, ext in zip(targets, ex.map(fetch_page_extract, targets)):
            if ext:
                lines.append(f"[page content from {link}]")
                lines.append(ext)
    return chr(10).join(lines)


def serper_search(query, num=8):
    """One Serper (Google) search; returns compact text results or ''."""
    import json as _json, os, urllib.request
    key = os.environ.get("SERPER_API_KEY")
    if not key:
        return ""
    try:
        req = urllib.request.Request(
            "https://google.serper.dev/search",
            data=_json.dumps({"q": query, "num": num}).encode(),
            headers={"X-API-KEY": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = _json.loads(r.read())
    except Exception:
        return ""
    lines = []
    for it in (data.get("organic") or [])[:num]:
        lines.append(f"- {it.get('title','')} | {it.get('link','')} | {(it.get('snippet') or '')[:200]}")
    return chr(10).join(lines)


def build_prompt(person, valid_roles, e4, search_text=""):
    t = person["talent"]
    gh = person.get("github_profile") or {}
    tid = t["person_id"]
    facts = [e["concept"] for e in person.get("evidence", []) if e["status"] == "FACT"]
    top_repos = get_top_repos(tid)
    contrib = get_contribution_repos(tid)
    contrib_line = ", ".join(f"{r[0]} ({r[1]} commits)" for r in contrib)
    repo_lines = "\n".join(
        f"- {r.get('full_name') or r.get('name')} "
        f"(stars {r.get('stargazers_count', 0)}, lang {r.get('language') or '?'}): "
        f"{(r.get('description') or '')[:120]}".strip()
        for r in top_repos
    )
    roles_list = "\n".join(f"- {cid}: {name}" for cid, name in valid_roles)

    # e4 outreach context
    e4r = e4.get(tid) or {}
    e4_lines = []
    for c in e4r.get("channels", []):
        ci = c.get("contact_info") or {}
        e4_lines.append(
            f"- {c['channel']}: {c['url']} (found via {c['source']}; "
            f"emails: {', '.join(ci.get('emails', [])) or 'none'})")
    e4_block = "\n".join(e4_lines) if e4_lines else "none found by scraper"
    search_block = search_text or 'no web search performed'

    return f"""You are classifying a crypto developer's GitHub profile into a talent ontology,
and finding their outreach channels (X / LinkedIn / email).

GitHub: {t.get('github')} ({t.get('name')})
Location: {gh.get('location') or '—'} | Blog: {gh.get('blog') or '—'} | \
Followers: {gh.get('followers', '?')} | Public repos: {gh.get('public_repos', '?')}
Top languages (repos): {fmt_counted(person.get('top_languages'))}
Top topics: {fmt_counted(person.get('top_topics'), 15)}
Top owned repos by stars:
{repo_lines or '—'}
Top contribution repos (commits to any repo incl. orgs, Electric Capital data):
{contrib_line or '—'}
Rules-derived skills (observed facts): {', '.join(facts[:20]) or '—'}

Social channels already known / scraped (rules, no AI):
{e4_block}

Web search results (Google via Serper):
{search_block}

Valid role concept ids (pick ONLY from this list):
{roles_list}

Rules:
- Infer roles ONLY from the evidence above. Weigh owned repos AND contribution repos; heavy commits to a well-known project are strong evidence. If the signal is thin, return an empty roles list.
- concept_id must be one of the valid ids. Never invent one.
- confidence is your honest uncertainty, 0-1.
- Seniority band: junior | mid | senior | staff | unknown. Prefer unknown over a guess.
- Summary: 2-3 lines a recruiter can skim. No hype.
- OUTREACH: use the web search results above to find channels for people
  with no known channel. Report a channel ONLY if confidence >= 0.4.
  match_basis must be honest: github_profile (listed on their GitHub), own_website
  (linked from their own site), login_match (same handle found via search),
  name_bio_match (name + matching bio/avatar), name_only (weakest).
  Never invent a URL. If nothing found, return an empty outreach list.
  Emails found inside scraped pages may be reported with match_basis own_website.
- LOCATION: if GitHub Location above is empty, use the web search results
  (LinkedIn / X / personal site bios) to find their city + country. Report only what you find;
  empty + confidence 0 + basis "none" if nothing. Never guess from the name."""


OUTREACH_CONCEPT = {"x": "Outreach channel (X)",
                    "linkedin": "Outreach channel (LinkedIn)",
                    "email": "Outreach channel (email)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default="gpt-6-luna")
    ap.add_argument("--triage", action="store_true",
                    help="skip people with >=10 strong FACTs (they don't need Luna)")
    ap.add_argument("--ids-file",
                    help="file with one talent_id per line: only enrich these")
    a = ap.parse_args()
    model_tag = f"{a.model}-unified"

    from openai import OpenAI
    import psycopg2

    client = OpenAI()
    import time
    conn = cur = None
    for attempt in range(5):
        try:
            conn = psycopg2.connect(db_url())
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT 1")
            break
        except Exception as ex:
            print(f"db connect attempt {attempt + 1} failed: {ex}", flush=True)
            time.sleep(5 * (attempt + 1))
    if cur is None:
        sys.exit("could not connect to Neon after 5 attempts")
    cur.execute(PROFILE_SCHEMA)
    cur.execute("ALTER TABLE talent_profiles ADD COLUMN IF NOT EXISTS "
                "location_text TEXT")
    cur.execute("ALTER TABLE talent_profiles ADD COLUMN IF NOT EXISTS "
                "location_confidence NUMERIC(3,2)")
    cur.execute(
        "SELECT concept_id, canonical_name FROM concepts WHERE concept_type = 'ROLE' "
        "ORDER BY concept_id"
    )
    valid_roles = cur.fetchall()
    if not valid_roles:
        cur.execute(
            "SELECT concept_id, canonical_name FROM concepts "
            "WHERE concept_id LIKE 'PM.ROLE.%' ORDER BY concept_id"
        )
        valid_roles = cur.fetchall()
    print(f"{len(valid_roles)} role concepts loaded", flush=True)

    e4 = load_e4()
    print(f"{len(e4)} e4 outreach records loaded", flush=True)

    people = json.loads(open(IN_JSON).read())
    if not isinstance(people, list):
        people = list(people.values())
    cur.execute("SELECT talent_id FROM talent_profiles WHERE llm_model = %s",
                (model_tag,))
    done = {r[0] for r in cur.fetchall()}
    todo = [p for p in people if p["talent"]["person_id"] not in done]
    if a.ids_file:
        want = {l.strip() for l in open(a.ids_file) if l.strip()}
        todo = [p for p in todo if p["talent"]["person_id"] in want]
        print(f"targeted run: {len(todo)} people from {a.ids_file}", flush=True)

    skipped = 0
    if a.triage:
        kept = []
        for p in todo:
            if triage_score(p) >= TRIAGE_FACT_THRESHOLD:
                skipped += 1
            else:
                kept.append(p)
        todo = kept
        print(f"triage: {skipped} rich profiles skipped, {len(todo)} need Luna",
              flush=True)

    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} people to enrich with {a.model} (+serper) [{model_tag}]",
          flush=True)

    for i, p in enumerate(todo, 1):
        tid = p["talent"]["person_id"]
        ensure_db()
        try:
            tt = p["talent"]
            need_search = not (e4.get(tid) or {}).get("channels") \
                or not (p.get("github_profile") or {}).get("location")
            search_text = ""
            if need_search:
                nm = tt.get("name") or ""
                gh = tt.get("github") or ""
                parts = []
                for q in (f'"{nm}" "{gh}" linkedin',
                          f'"{nm}" "{gh}" twitter OR x.com'):
                    r = serper_search_rich(q, fetch_top=2)
                    if r:
                        parts.append(r)
                search_text = chr(10).join(parts)
            resp = client.responses.parse(
                model=a.model,
                input=[{"role": "user",
                        "content": build_prompt(p, valid_roles, e4, search_text)}],
                text_format=EnrichmentOutput,
            )
            out = resp.output_parsed
        except Exception as ex:
            print(f"[{i}/{len(todo)}] {tid} LLM error: {ex}", flush=True)
            time.sleep(5)
            continue

        # replace, don't stack: drop roles any earlier LLM run (e3, or e5 with another model) wrote
        cur.execute(
            "DELETE FROM talent_evidence WHERE talent_id = %s AND concept_type = 'ROLE' "
            "AND source LIKE 'llm:%%'",
            (tid,),
        )
        loc = out.location or Location()
        loc_text = ", ".join(x for x in (loc.city, loc.country) if x) or None
        gh_raw = ((p.get("github_profile") or {}).get("location") or "").strip() or None
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from viewer_api.location_norm import normalize as _norm
        _gd, _gc = _norm(gh_raw)
        _ad, _ac = _norm(loc_text)
        gh_loc, gh_country = _gd, _gc
        loc_text, ai_country = _ad, _ac
        resolved_loc = gh_loc or loc_text
        resolved_country = gh_country or ai_country
        for r in out.roles:
            if not any(cid == r.concept_id for cid, _ in valid_roles):
                continue
            name = next(n for cid, n in valid_roles if cid == r.concept_id)
            eid = f"ev_llm_{model_tag}_{tid}_{r.concept_id}".replace(":", "_")
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_id, concept_name, concept_type,
                    status, usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,%s,'ROLE','INFERENCE','OBSERVED_USAGE',%s,%s,%s,now())
                   ON CONFLICT (evidence_id) DO UPDATE SET
                     confidence=EXCLUDED.confidence, note=EXCLUDED.note,
                     enriched_at=now(), loaded_at=now()""",
                (eid, tid, r.concept_id, name, r.confidence,
                 f"llm:{a.model}", r.reasoning),
            )

        # outreach -> FACT or INFERENCE rows
        for o in out.outreach:
            if o.confidence < 0.4 or not o.url:
                continue
            basis = o.match_basis
            status = "FACT" if basis in ("github_profile", "own_website") else "INFERENCE"
            concept = OUTREACH_CONCEPT.get(o.channel, f"Outreach channel ({o.channel})")
            eid = (f"ev_outreach_{model_tag}_{tid}_{o.channel}"
                   ).replace(":", "_").replace("/", "_")
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_id, concept_name, concept_type,
                    status, usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,NULL,%s,'IDENTITY',%s,'DECLARED_USAGE',%s,%s,%s,now())
                   ON CONFLICT (evidence_id) DO UPDATE SET
                     confidence=EXCLUDED.confidence, note=EXCLUDED.note,
                     enriched_at=now(), loaded_at=now()""",
                (eid, tid, concept, status, o.confidence,
                 f"llm:{a.model}",
                 f"{o.url} | basis={basis} | {o.reasoning}"),
            )

        # location as INFERENCE evidence (only if found with some confidence)
        if loc_text and loc.confidence >= 0.4:
            cur.execute(
                """INSERT INTO talent_evidence
                   (evidence_id, talent_id, concept_name, concept_type, status,
                    usage_level, confidence, source, note, enriched_at)
                   VALUES (%s,%s,%s,'SYSTEM','INFERENCE','DECLARED_USAGE',%s,%s,%s,now())
                   ON CONFLICT (evidence_id) DO UPDATE SET
                     concept_name=EXCLUDED.concept_name, confidence=EXCLUDED.confidence,
                     source=EXCLUDED.source, note=EXCLUDED.note, enriched_at=now()""",
                (f"e5loc:{tid}", tid, f"location:{resolved_loc or loc_text}", loc.confidence,
                 f"llm:{a.model}", f"web {loc.basis or 'profile'}"),
            )
        cur.execute(
            """INSERT INTO talent_profiles
               (talent_id, summary, seniority_band, seniority_confidence, llm_model,
                location_text, location_confidence, location_github, location,
                location_country)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (talent_id) DO UPDATE SET
                 summary=EXCLUDED.summary,
                 seniority_band=EXCLUDED.seniority_band,
                 seniority_confidence=EXCLUDED.seniority_confidence,
                 llm_model=EXCLUDED.llm_model,
                 location_text=EXCLUDED.location_text,
                 location_confidence=EXCLUDED.location_confidence,
                 location_github=EXCLUDED.location_github,
                 location=EXCLUDED.location,
                 location_country=EXCLUDED.location_country,
                 updated_at=now()""",
            (tid, out.summary, out.seniority.band, out.seniority.confidence,
             model_tag, loc_text, loc.confidence, gh_loc, resolved_loc,
             resolved_country),
        )
        # flag for the viewer UI immediately
        try:
            flag_ai_enriched(tid, model_tag)
        except Exception as ex:
            print(f"[{i}/{len(todo)}] {tid} flag warning: {ex}", flush=True)
        if i % 10 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] {tid}: {len(out.roles)} roles, "
                  f"{len(out.outreach)} channels, seniority {out.seniority.band}",
                  flush=True)


if __name__ == "__main__":
    main()
