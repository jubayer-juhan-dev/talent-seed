"""Public, server-rendered talent profile at /p/<person_id> (linked from the shortlist pages).

Same trust level as the /s/ shortlist pages: no access key, read-only, and NEVER an email address. Contact emails are
only counted ("yes/no"); every string that reaches the page is HTML-escaped and scrubbed with EMAIL_RE, and mailto:
links are dropped. Data: DuckDB talent_seed (via queries.api_person), Neon talent_evidence/talent_profiles
(neon_enrichment), the tier-1 GitHub cache (profile + repos) and jobs.add_readiness for the channel flags.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from . import client_enrichment, github_profile, jobs, neon_enrichment, queries

PERSON_ID = re.compile(r"(gh|odd):\d+")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CONCEPT_TYPES = ("ROLE", "SKILL", "TOOL", "SYSTEM", "KNOWLEDGE", "CAPABILITY")
GROUPS = (("client", "AI-judged by an MCP client"), ("llm", "AI-inferred (pipeline)"), ("evidence", "Observed from GitHub & components"))


def _t(v) -> str:
    """Escaped, email-scrubbed text."""
    return html.escape(EMAIL_RE.sub("[email hidden]", "" if v is None else str(v)))


def _url(v) -> str | None:
    """http(s) URL that is not an email, else None."""
    v = (v or "").strip()
    return v if urlparse(v).scheme in ("http", "https") and "@" not in urlparse(v).netloc and not EMAIL_RE.search(v) else None


def _group(source: str) -> str:
    s = source or ""
    return "client" if s.startswith("client:") else "llm" if s.startswith("llm:") else "evidence"


def _link(url, label):
    u = _url(url)
    return f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener noreferrer nofollow">{_t(label)}</a>' if u else None


def data(con, pid: str) -> dict | None:
    out = queries.api_person(con, {"id": [pid]})
    if "error" in out:
        return None
    gh = client_enrichment._github([pid]).get(pid)
    enr = neon_enrichment.fetch(pid) or {}
    prof = github_profile.fetch(pid) or {}
    ready = jobs.add_readiness(con, {"items": [{"talent_id": pid}]})["items"][0]["readiness"]
    return {"person": out["person"], "ecosystems": out["ecosystems"], "gh": gh, "enr": enr, "prof": prof, "ready": ready}


def render(d: dict) -> str:
    p, enr, prof, ready = d["person"], d["enr"], d["prof"], d["ready"]
    login = (d["gh"][0] if d["gh"] else None) or p.get("github_login")
    name = p.get("display_name") or login or p["person_id"]
    loc = ", ".join(x for x in (enr.get("location") or p.get("location") or prof.get("location"), p.get("country")) if x) or "—"
    badge = ""
    if p.get("ai_enriched"):
        badge = f'<span class="ai" title="Enriched by {_t(p.get("ai_enriched_by") or "AI")}">✦ AI-enriched</span>'
    seg = [x for x in (p.get("priority_cohort"), p.get("activity_segment"), p.get("tenure_segment"), p.get("exclusivity")) if x]
    chips = "".join(f'<span class="tag">{_t(s.replace("_", " ").title() if s != p.get("priority_cohort") else s)}</span>' for s in seg)
    eco = "".join(f'<span class="tag">{_t(e)}</span>' for e in (p.get("top_level_ecosystems") or [])[:12])

    bio = (d["gh"][1].get("bio") if d["gh"] else None) or prof.get("bio")
    repos = sorted([r for r in (d["gh"][2] if d["gh"] else []) if isinstance(r, dict)],
                   key=lambda r: (r.get("fork") is True, -(r.get("stargazers_count") or 0)))
    langs = {}
    for r in repos:
        if r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    lang_html = "".join(f'<span class="tag">{_t(k)} · {v}</span>' for k, v in sorted(langs.items(), key=lambda kv: -kv[1])[:10])
    repo_rows = "".join(
        f'<tr><td>{_link(r.get("html_url"), r.get("name")) or _t(r.get("name"))}{" <i>fork</i>" if r.get("fork") else ""}</td>'
        f'<td>{_t(r.get("description"))}</td><td>{_t(r.get("language"))}</td><td class="n">{r.get("stargazers_count") or 0:,}</td></tr>'
        for r in repos[:12])

    # concepts: every real concept row, grouped by where it came from; client rows first
    groups = {k: [] for k, _ in GROUPS}
    for e in enr.get("evidence") or []:
        if e.get("concept_type") in CONCEPT_TYPES and e.get("status") != "UNKNOWN":
            groups[_group(e.get("source"))].append(e)
    concept_html = ""
    for key, title in GROUPS:
        rows = groups[key]
        if not rows:
            continue
        items = "".join(
            f'<li class="{"cl" if key == "client" else ""}"><b>{_t(e["concept_name"])}</b> '
            f'<span class="meta">{_t(e["concept_type"].title())} · {_t(e["status"].title())} · '
            f'{_t((e.get("usage_level") or "").replace("_", " ").lower())} · {round(e["confidence"] * 100)}%</span>'
            f'<div class="note">{_t(e.get("note"))}</div>'
            f'<div class="src">{_t(e.get("source"))}</div></li>' for e in rows)
        concept_html += f'<h3>{_t(title)} <span class="meta">({len(rows)})</span></h3><ul class="concepts">{items}</ul>'

    em = ready["email"]
    x, li = ready.get("x_handle"), ready.get("linkedin_url")
    channels = (
        f'<span class="{"ok" if em["has"] == "yes" else "no"}">📧 Email: {"yes" if em["has"] == "yes" else "no"}</span>'
        f'<span class="{"ok" if x else "no"}">𝕏 X: {(_link("https://x.com/" + x.lstrip("@"), x) if x and re.fullmatch(r"@?\w+", x) else "yes") if x else "no"}</span>'
        f'<span class="{"ok" if li else "no"}">in LinkedIn: {(_link(li, "profile") or "yes") if li else "no"}</span>'
        f'<span class="{"ok" if ready["telegram"] == "yes" else "no"}">✈️ Telegram: {ready["telegram"]}</span>')
    gh_link = _link(f"https://github.com/{login}", f"@{login}") if login and re.fullmatch(r"[\w-]+", login) else ""
    site = _link(prof.get("website"), prof.get("website")) if prof.get("website") else ""
    summary = f'<p class="summary">{_t(enr.get("summary"))}</p>' if enr.get("summary") else ""
    stats = " · ".join(x for x in (
        f'{p["commit_count"]:,} commits' if p.get("commit_count") else "",
        f'{p["repository_count"]:,} repos' if p.get("repository_count") else "",
        f'first crypto commit {p["first_crypto_commit_date"]}' if p.get("first_crypto_commit_date") else "",
        f'last active {p["last_activity_date"]}' if p.get("last_activity_date") else "") if x)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer">
<title>{_t(name)} — Talent profile · GoodHive</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#FFFBEB;color:#1C1917}}
header{{background:#fff;border-bottom:3px solid #F59E0B;padding:26px 0 18px}} .wrap{{max-width:900px;margin:0 auto;padding:0 16px}}
h1{{font-size:28px;margin:6px 0 2px}} h2{{font-size:18px;margin:28px 0 8px;border-bottom:1px solid #FDE68A;padding-bottom:4px}} h3{{font-size:15px;margin:16px 0 6px}}
.sub{{color:#57534E;font-size:14px;margin:2px 0}} .meta{{color:#78716C;font-size:12px;font-weight:400}}
.badge{{display:inline-block;background:#FEF3C7;color:#92400E;border:1px solid #F59E0B;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:600}}
.ai{{display:inline-block;background:#1C1917;color:#FCD34D;border-radius:999px;padding:3px 12px;font-size:13px;font-weight:700;margin-left:8px;vertical-align:middle}}
.tag{{display:inline-block;background:#F5F5F4;border-radius:6px;padding:2px 8px;font-size:12px;margin:2px 4px 2px 0}}
.channels span{{display:inline-block;margin:4px 14px 4px 0;font-size:14px}} .no{{opacity:.4}} .ok{{font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:#fff;border:1px solid #E7E5E4;border-radius:10px}}
td,th{{text-align:left;padding:7px 10px;border-bottom:1px solid #F5F5F4;vertical-align:top}} td.n{{text-align:right}}
ul.concepts{{list-style:none;margin:0;padding:0}} ul.concepts li{{background:#fff;border:1px solid #E7E5E4;border-radius:10px;padding:10px 14px;margin:6px 0}}
ul.concepts li.cl{{border-color:#F59E0B;box-shadow:0 0 0 2px #FDE68A}} .note{{font-size:13px;color:#44403C;margin-top:3px}} .src{{font-size:11px;color:#A8A29E;margin-top:2px}}
.summary{{background:#fff;border:1px solid #FDE68A;border-radius:10px;padding:12px;font-size:14px}} a{{color:#B45309}}
footer{{color:#A8A29E;font-size:12px;padding:24px 0 40px}}
</style></head><body>
<header><div class="wrap"><span class="badge">🍯 GoodHive · Talent profile</span>
<h1>{_t(name)}{badge}</h1>
<div class="sub">{gh_link} · {_t(loc)}{(" · " + site) if site else ""}</div>
<div class="sub">{chips}</div><div class="sub meta">{_t(stats)}</div></div></header>
<div class="wrap">
{summary}
<h2>Reachability</h2><div class="channels">{channels}</div>
<p class="meta">Email addresses are never shown on this page; only whether one is known.</p>
{f'<h2>GitHub</h2><p>{_t(bio)}</p>' if bio else '<h2>GitHub</h2>'}
<div>{lang_html}</div>
{f'<h3>Top repositories</h3><table><tr><th>Repo</th><th>Description</th><th>Language</th><th>★</th></tr>{repo_rows}</table>' if repo_rows else '<p class="meta">No repository details cached for this person.</p>'}
{f'<h2>Ecosystems</h2><div>{eco}</div>' if eco else ''}
<h2>Concepts &amp; evidence</h2>
{concept_html or '<p class="meta">No concept evidence recorded yet.</p>'}
<footer>Data: Electric Capital Open Dev Data (CC BY 4.0), GitHub, GoodHive enrichment · {_t(p["person_id"])}</footer>
</div></body></html>"""
    return EMAIL_RE.sub("[email hidden]", page)
