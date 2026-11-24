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
        badge = f'<span class="ai" title="Enriched by {_t(p.get("ai_enriched_by") or "AI")}"><svg><use href="#i-spark"/></svg>AI-enriched</span>'
    else:
        badge = '<span class="ai no">Not AI-enriched</span>'
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
        f'<span class="{"ok" if em["has"] == "yes" else "no"}"><svg><use href="#i-mail"/></svg>Email · {"yes" if em["has"] == "yes" else "no"}</span>'
        f'<span class="{"ok" if x else "no"}"><svg><use href="#i-x"/></svg>X · {(_link("https://x.com/" + x.lstrip("@"), x) if x and re.fullmatch(r"@?\w+", x) else "yes") if x else "no"}</span>'
        f'<span class="{"ok" if li else "no"}"><svg><use href="#i-in"/></svg>LinkedIn · {(_link(li, "profile") or "yes") if li else "no"}</span>'
        f'<span class="{"ok" if ready["telegram"] == "yes" else "no"}"><svg><use href="#i-tg"/></svg>Telegram · {ready["telegram"]}</span>')
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
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<title>{_t(name)} — Talent profile · GoodHive</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;background:#FAF8F5;color:#1B1611;-webkit-font-smoothing:antialiased}}
header{{background:#fff;border-bottom:1px solid #EAE3D8;padding:30px 0 22px}} .wrap{{max-width:920px;margin:0 auto;padding:0 20px}}
h1{{font-size:30px;margin:10px 0 4px;letter-spacing:-.02em}} h2{{font-size:18px;margin:32px 0 10px;letter-spacing:-.01em}} h3{{font-size:15px;margin:20px 0 8px}}
.sub{{color:#6F6558;font-size:14.5px;margin:3px 0}} .meta{{color:#A79B8A;font-size:12.5px;font-weight:400}}
.badge{{display:inline-flex;align-items:center;gap:7px;background:#FFF4DF;color:#9A4A00;border:1px solid #F6DFB2;border-radius:999px;padding:4px 12px;font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase}}
.badge svg{{width:14px;height:14px}}
.ai{{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#FFB020,#F06410);color:#fff;border-radius:999px;padding:4px 13px;font-size:12.5px;font-weight:700;margin-left:10px;vertical-align:middle;box-shadow:0 4px 10px -4px rgba(240,100,16,.6)}}
.ai svg{{width:13px;height:13px}}
.ai.no{{background:#F4F1EC;color:#A79B8A;border:1px solid #EAE3D8;box-shadow:none;font-weight:600}}
.tag{{display:inline-block;background:#F6F3EF;color:#57493A;border-radius:7px;padding:3px 9px;font-size:12px;font-weight:500;margin:2px 4px 2px 0}}
.channels{{display:flex;gap:9px;flex-wrap:wrap}}
.channels span{{display:inline-flex;align-items:center;gap:7px;font-size:13px;font-weight:600;background:#FFF4DF;color:#1B1611;border-radius:10px;padding:8px 12px}}
.channels span svg{{width:15px;height:15px}}
.channels span.no{{background:#F6F3EF;color:#A79B8A;opacity:.6;font-weight:500}}
.channels span a{{color:#9A4A00}}
table{{width:100%;border-collapse:collapse;font-size:14px;background:#fff;border:1px solid #EAE3D8;border-radius:14px;overflow:hidden}}
td,th{{text-align:left;padding:9px 12px;border-bottom:1px solid #F4EFE7;vertical-align:top}} td.n{{text-align:right;font-weight:600}}
ul.concepts{{list-style:none;margin:0;padding:0}} ul.concepts li{{background:#fff;border:1px solid #EAE3D8;border-radius:14px;padding:12px 16px;margin:7px 0}}
ul.concepts li.cl{{border-color:#F59E0B;box-shadow:0 0 0 2px #FBD88A}} .note{{font-size:13px;color:#44403C;margin-top:3px}} .src{{font-size:11px;color:#A8A29E;margin-top:2px}}
.summary{{background:#FFF9EC;border:1px solid #F3E3BC;border-radius:16px;padding:16px 18px;font-size:14.5px;line-height:1.6}} a{{color:#9A4A00}}
footer{{color:#A79B8A;font-size:12px;padding:28px 0 44px}}
</style></head><body>
<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><symbol id="i-hex" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2.5 20 7v10l-8 4.5L4 17V7z"/><circle cx="12" cy="10" r="2.6" fill="currentColor" stroke="none"/><path d="M7.5 17.5c.8-2.3 2.5-3.4 4.5-3.4s3.7 1.1 4.5 3.4"/></symbol><symbol id="i-spark" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2.5 14 9l6.5 2-6.5 2-2 6.5L10 13 3.5 11 10 9zM19 15.5l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9z"/></symbol><symbol id="i-mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 7 8.5 6 8.5-6"/></symbol><symbol id="i-x" viewBox="0 0 24 24" fill="currentColor"><path d="M17.9 3H21l-6.8 7.8L22.2 21h-6.3l-4.9-6.4L5.4 21H2.2l7.3-8.3L1.8 3h6.4l4.4 5.9zm-1.1 16.1h1.7L7.4 4.8H5.6z"/></symbol><symbol id="i-in" viewBox="0 0 24 24" fill="currentColor"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9h4v12H3zM9 9h3.8v1.7h.1c.5-1 1.8-2 3.7-2 4 0 4.7 2.6 4.7 6V21h-4v-5.5c0-1.3 0-3-1.9-3s-2.2 1.4-2.2 2.9V21H9z"/></symbol><symbol id="i-tg" viewBox="0 0 24 24" fill="currentColor"><path d="M21.9 4.4 18.8 19c-.2 1-.8 1.3-1.7.8l-4.7-3.5-2.3 2.2c-.3.3-.5.5-1 .5l.4-4.9 8.9-8c.4-.4-.1-.6-.6-.2L7.6 13.2 2.8 11.7c-1-.3-1-1 .2-1.5l18.6-7.2c.9-.3 1.6.2 1.3 1.4z"/></symbol></defs></svg>
<header><div class="wrap"><span class="badge"><svg><use href="#i-hex"/></svg>GoodHive · Talent profile</span>
<h1>{_t(name)}{badge}</h1>
<div class="sub">{gh_link} · {_t(loc)}{(" · " + site) if site else ""}</div>
<div class="sub">{chips}</div><div class="sub meta">{_t(stats)}</div></div></header>
<div class="wrap">
{summary}
<h2>Reachability</h2><div class="channels">{channels}</div>
<p class="meta">Email addresses are never shown on this page; only whether one is known.</p>
{f'<h2>GitHub</h2><p>{_t(bio)}</p>' if bio else '<h2>GitHub</h2>'}
<div>{lang_html}</div>
{f'<h3>Top repositories</h3><table><tr><th>Repo</th><th>Description</th><th>Language</th><th>Stars</th></tr>{repo_rows}</table>' if repo_rows else '<p class="meta">No repository details cached for this person.</p>'}
{f'<h2>Ecosystems</h2><div>{eco}</div>' if eco else ''}
<h2>Concepts &amp; evidence</h2>
{concept_html or '<p class="meta">No concept evidence recorded yet.</p>'}
<footer>Data: Electric Capital Open Dev Data (CC BY 4.0), GitHub, GoodHive enrichment · {_t(p["person_id"])}</footer>
</div></body></html>"""
    return EMAIL_RE.sub("[email hidden]", page)
