"""MCP server: lets Claude (Claude Code, Claude Desktop, …) use Talent Seed directly.

Run:   uv run python -m viewer_api.mcp_server          (stdio; Claude Code starts it from .mcp.json)
Web:   `remote` below, served at /mcp by the viewer (viewer_api/main.py) for other users

Same queries as the viewer API (viewer_api/queries.py), called in-process on a read-only DuckDB connection,
so no running viewer or access key is needed. The only write is set_ai_enriched, which writes
data/enrichment.sqlite the same way scripts/set_ai_enriched.py does.
"""

import os
import html
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlencode

import duckdb
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import queries
from .enrichment import SCHEMA
from .settings import ENRICHMENT, EXPORT_LIMIT, ROOT

PERSON_ID = re.compile(r"(gh|odd):\d+")
EXPORTS = ROOT / "exports"
READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

mcp = MCPServer(
    "talent-seed",
    instructions="Crypto developer talent data (Electric Capital Open Dev Data, CC BY 4.0). People have ids "
                 "gh:<github user id> or odd:<id>. Cohorts: P1 (highest priority) to P3, HOLD = parked. "
                 "Start with overview or meta for the filter values, search_people to find people, get_person for "
                 "a full profile. Contact emails are UNVERIFIED and are personal data: only use them for the "
                 "recruiting purpose the user states.",
)


@contextmanager
def db():
    try:
        con = queries.connect()
    except duckdb.IOException:
        raise ToolError("The database is being rebuilt (scripts/m4_build_talent_seed.py). Try again in a few minutes.")
    try:
        yield con
    finally:
        con.close()


def filters(**kw) -> dict[str, list[str]]:
    """Tool arguments -> the parse_qs-style dict queries.py takes (lists joined the way the web app sends them)."""
    out = {}
    for k, v in kw.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, bool):
            v = "1" if v else "0"
        elif isinstance(v, list):
            v = ("|" if k == "eco" else ",").join(v)
        out[k] = [str(v)]
    return out


Cohort = Literal["P1", "P2", "P3", "HOLD"]
Sort = Literal["commits", "last_activity", "first_commit", "repos", "ecosystems", "active_days", "name"]


def people_filters(cohort, activity, tenure, exclusivity, country, chain, ecosystems, ids, hide_flagged, ai_enriched, text,
                   sort, direction, **extra):
    return filters(cohort=cohort, activity=activity, tenure=tenure, exclusivity=exclusivity, country=country, chain=chain,
                   eco=ecosystems, ids=ids, hide_flagged=hide_flagged, ai_enriched=ai_enriched, q=text, sort=sort,
                   dir=direction, **extra)


@mcp.tool(annotations=READ)
def meta() -> dict[str, Any]:
    """Data snapshot info and the values the filters accept: cohorts, top chains and countries with counts."""
    with db() as con:
        return queries.jsonable(queries.api_meta(con, {}))


@mcp.tool(annotations=READ)
def overview() -> dict[str, Any]:
    """Headline numbers: people per cohort, top chains (with P1 counts), tenure x activity mix, top countries."""
    with db() as con:
        return queries.jsonable(queries.api_overview(con, {}))


@mcp.tool(annotations=READ)
def search_ecosystems(text: Annotated[str, Field(description="part of a chain or project name, e.g. 'uni'")]) -> dict[str, Any]:
    """Find exact chain / sub-ecosystem names (for search_people's chain and ecosystems filters), with people counts."""
    with db() as con:
        return queries.jsonable(queries.api_ecosystems(con, {"q": [text]}))


@mcp.tool(annotations=READ)
def search_people(
    cohort: list[Cohort] | None = None,
    activity: list[Literal["FULL_TIME", "PART_TIME", "ONE_TIME", "UNKNOWN"]] | None = None,
    tenure: list[Literal["ESTABLISHED", "EMERGING", "NEWCOMER", "UNKNOWN"]] | None = None,
    exclusivity: list[Literal["EXCLUSIVE", "MULTICHAIN", "UNKNOWN"]] | None = None,
    country: Annotated[list[str] | None, Field(description="country names as meta returns them")] = None,
    chain: Annotated[str | None, Field(description="one top-level chain, e.g. 'Ethereum'")] = None,
    ecosystems: Annotated[list[str] | None, Field(description="chains or projects; matches any (see search_ecosystems)")] = None,
    ids: Annotated[list[str] | None, Field(description="person ids")] = None,
    hide_flagged: Annotated[bool, Field(description="hide probable bots and GitHub conflicts")] = True,
    ai_enriched: Annotated[bool | None, Field(description="true = AI-enriched only, false = not enriched yet")] = None,
    text: Annotated[str | None, Field(description="name or login substring, exact email, or person id")] = None,
    sort: Sort = "active_days",
    direction: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Field(ge=1)] = 1,
    page_size: Annotated[int, Field(ge=1, le=50, description="rows per page; keep small, rows are wide")] = 20,
) -> dict[str, Any]:
    """Filter and rank people, page_size (default 20, max 50) per page. Returns total matches and the rows for this page."""
    q = people_filters(cohort, activity, tenure, exclusivity, country, chain, ecosystems, ids, hide_flagged, ai_enriched,
                       text, sort, direction, page=page)
    with db() as con:
        return queries.jsonable(queries.api_people(con, q, page_size))


@mcp.tool(annotations=READ)
def get_person(person_id: Annotated[str, Field(description="gh:… or odd:…")]) -> dict[str, Any]:
    """Full profile: person row, linked developer ids, contact points, ecosystems, repos and top repos."""
    with db() as con:
        out = queries.api_person(con, {"id": [person_id]})
    if "error" in out:
        raise ToolError(out["error"])
    from . import enrichment as _enr
    _found = _enr.lookup([person_id])
    out["ai_enriched"] = person_id in _found
    if person_id in _found:
        out["ai_enriched_by"] = _found[person_id][1]
    return queries.jsonable(out)


@mcp.tool(annotations=READ)
def get_person_enrichment(person_id: Annotated[str, Field(description="gh:… or odd:…")]) -> dict[str, Any]:
    """AI enrichment for one person: LLM summary, inferred roles and the evidence rows behind them."""
    from . import neon_enrichment
    out = neon_enrichment.fetch(person_id)
    if out is None:
        raise ToolError("No AI enrichment for this person.")
    return queries.jsonable(out)


@mcp.tool(annotations=READ)
def get_github_profile(person_id: Annotated[str, Field(description="gh:… or odd:…")]) -> dict[str, Any]:
    """GitHub profile details: name, bio, company, location, website, X and LinkedIn (for outreach)."""
    from . import github_profile
    out = github_profile.fetch(person_id)
    if out is None:
        raise ToolError("GitHub profile not fetched yet for this person.")
    return queries.jsonable(out)


@mcp.tool(annotations=READ)
def list_concepts() -> list[dict[str, Any]]:
    """Talent Ontology: every active concept (roles, skills, tools, systems, knowledge, capabilities) with its id."""
    from . import jobs as jobmod
    return queries.jsonable(jobmod.list_concepts())


@mcp.tool(annotations=READ)
def list_jobs() -> list[dict[str, Any]]:
    """All active jobs with requirement and match counts. Use get_job for one job, match_job for its candidates."""
    from . import jobs as jobmod
    return queries.jsonable(jobmod.list_jobs())


@mcp.tool(annotations=READ)
def get_job(job_id: Annotated[str, Field(description="job id from list_jobs")]) -> dict[str, Any]:
    """One job: title, company, description and its required / nice-to-have ontology concepts."""
    from . import jobs as jobmod
    out = jobmod.get_job(job_id)
    if out is None:
        raise ToolError("Job not found.")
    return queries.jsonable(out)


@mcp.tool(annotations=READ)
def match_job(
    job_id: Annotated[str, Field(description="job id from list_jobs")],
    pool: Annotated[Literal["all", "ai"], Field(description="all = everyone with evidence, ai = AI-enriched only")] = "all",
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """Ranked candidates for a job, best first, with a per-concept evidence breakdown for each."""
    from . import jobs as jobmod
    if jobmod.get_job(job_id) is None:
        raise ToolError("Job not found.")
    out = jobmod.match(job_id, pool=pool, limit=limit, offset=offset)
    out["offset"] = offset
    with db() as con:
        return queries.jsonable(jobmod.add_readiness(con, jobmod.add_enrichment_flag(jobmod.add_people(con, out))))


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
def match_job_text(
    job_description: Annotated[str, Field(description="raw job posting text", min_length=40)],
    title: Annotated[str, Field(description="role title (also drives the title->role rules)")] = "",
    company: str = "",
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    """Extract required / nice-to-have ontology concepts from raw job text (the j2 extraction behind match_job; it
    stores the job like POST /api/jobs and makes one LLM call), then rank candidates with match_job's scoring.
    Same shape as match_job plus job_id, requirements and growth_candidates; every item has a readiness block."""
    from . import jobs as jobmod
    try:
        out = jobmod.match_text(job_description, title, company, limit)
    except Exception as e:
        raise ToolError(f"Extraction or matching failed: {type(e).__name__}: {e}")
    out["offset"] = 0
    with db() as con:
        return queries.jsonable(jobmod.add_readiness(con, jobmod.add_enrichment_flag(jobmod.add_people(con, out))))


class ConceptRequirement(BaseModel):
    concept_id: Annotated[str, Field(description="id from list_concepts, e.g. SKILL.0051")]
    requirement: Annotated[Literal["required", "nice_to_have", "preferred"],
                           Field(description="required, or nice_to_have (preferred is accepted as an alias)")]


@mcp.tool(annotations=READ)
def match_by_concepts(
    requirements: Annotated[list[ConceptRequirement], Field(min_length=1, max_length=60,
                            description="[{concept_id, requirement}] you picked from list_concepts")],
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    """Rank the talent pool against ontology concepts YOU chose (read list_concepts, pick the concepts a job needs,
    mark each required / nice_to_have). Deterministic scoring only: the same code as match_job, no LLM call, no
    writes. Use it when match_job_text can't extract concepts. Same shape as match_job (with readiness per item)
    plus requirements; unknown concept_ids are an error."""
    from . import jobs as jobmod
    reqs = [{"concept_id": r.concept_id.strip(),
             "requirement": "nice_to_have" if r.requirement == "preferred" else r.requirement} for r in requirements]
    dup = sorted({r["concept_id"] for r in reqs if sum(x["concept_id"] == r["concept_id"] for x in reqs) > 1})
    if dup:
        raise ToolError(f"Duplicate concept_ids: {', '.join(dup)}. List each concept once.")
    out, unknown = jobmod.match_concepts(reqs, pool="all", limit=limit)
    if unknown:
        raise ToolError(f"Unknown concept_id(s): {', '.join(unknown)}. Use ids from list_concepts.")
    out["offset"] = 0
    out["requirements"] = reqs
    with db() as con:
        return queries.jsonable(jobmod.add_readiness(con, jobmod.add_enrichment_flag(jobmod.add_people(con, out))))


@mcp.tool(annotations=READ)
def get_enrichment_batch(
    limit: Annotated[int, Field(ge=1, le=25)] = 10,
    only_unenriched: Annotated[bool, Field(description="skip people already flagged AI-enriched")] = True,
) -> list[dict[str, Any]]:
    """Talents that still need AI enrichment, each with an evidence bundle YOU judge from: GitHub bio, repos (name,
    description, language, topics), primary languages and their existing concept assignments. Read-only, local data
    only (no network, no LLM). Pick concepts from list_concepts that the evidence genuinely supports, then call
    submit_enrichment. Profile READMEs are not stored locally, so the bundle has none."""
    from . import client_enrichment
    with db() as con:
        return queries.jsonable(client_enrichment.batch(con, limit, only_unenriched))


class EnrichedConcept(BaseModel):
    concept_id: Annotated[str, Field(description="id from list_concepts, e.g. PM.SKILL.0002")]
    evidence: Annotated[str, Field(min_length=10, max_length=500,
                                   description="one or two sentences citing the repo / bio text that supports it")]
    confidence: Annotated[float, Field(ge=0, le=1, description="your confidence that the person has this concept")]
    usage_level: Annotated[Literal["OBSERVED_USAGE", "CONTRIBUTOR_USAGE", "ADVANCED_USAGE", "DECLARED_USAGE", "DECLARED"],
                           Field(description="OBSERVED_USAGE = seen in their repos; CONTRIBUTOR_USAGE = sustained "
                                             "contributions; ADVANCED_USAGE = deep expertise; DECLARED(_USAGE) = only "
                                             "claimed in bio")]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def submit_enrichment(
    talent_id: Annotated[str, Field(description="gh:… or odd:… from get_enrichment_batch")],
    concepts: Annotated[list[EnrichedConcept], Field(min_length=1, max_length=40)],
    source_note: Annotated[str | None, Field(description="who judged it, e.g. 'claude-opus via MCP client'", max_length=60)] = None,
) -> dict[str, Any]:
    """Store concepts you judged from a talent's evidence (as INFERENCE rows that match_job scoring uses) and mark
    them AI-enriched. Every concept_id must exist in the ontology or the whole submission is rejected. Resubmitting
    replaces this talent's earlier client-submitted rows only; GitHub-derived and other rows are never touched."""
    from . import client_enrichment
    if not PERSON_ID.fullmatch(talent_id):
        raise ToolError(f"Not a person id: {talent_id}")
    with db() as con:
        if not con.execute("SELECT 1 FROM talent_seed WHERE person_id = ?", [talent_id]).fetchone():
            raise ToolError(f"Unknown talent_id: {talent_id}")
    try:
        return client_enrichment.submit(talent_id, [c.model_dump() for c in concepts], source_note)
    except ValueError as e:
        raise ToolError(str(e))


WWW = Path(os.environ.get("TALENT_SEED_WWW", "/var/lib/docker/volumes/n8n_caddy_data/_data/www"))
SHORTLIST_BASE = os.environ.get("TALENT_SEED_SHORTLIST_BASE", "https://talent.jubayerjuhan.site/s/")
SHORTLIST_TEMPLATE = Path(__file__).with_name("shortlist_template.html")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _slug(*parts: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower()).strip("-")[:80] or "shortlist"


def _talent(rank: int, it: dict) -> dict:
    bd = [b for b in it.get("breakdown") or [] if (b.get("coverage") or 0) > 0]
    bd.sort(key=lambda b: (-b["coverage"], b.get("requirement") != "required", b.get("concept_name", "")))
    reasons = it.get("reasons") or [
        [b["concept_name"], ", ".join(x for x in (b.get("evidence_status"),
                                                  (b.get("usage_level") or "").replace("_", " ").lower()) if x)]
        for b in bd[:3]]
    skills = it.get("skills") or [b["concept_name"] for b in bd][:6]
    rd = it.get("readiness") or {}
    yn = lambda v: "yes" if v else "no"
    em = rd.get("email")
    em = em.get("has") == "yes" if isinstance(em, dict) else em == "yes"
    score = it.get("score") or 0
    return {"rank": rank, "id": it.get("talent_id") or it.get("person_id") or it.get("id") or "", "name": it.get("name") or it.get("github_login") or it.get("talent_id") or it.get("person_id") or "Unknown prospect",
            "github": it.get("github_login") or "", "score": round(score * 100) if score <= 1 else round(score),
            "reasons": [list(map(str, r[:2])) for r in reasons[:3]], "skills": [str(x) for x in skills[:6]],
            "location": it.get("country") or it.get("location") or "—",
            "ai_enriched": bool(it.get("ai_enriched")), "ai_enriched_by": it.get("ai_enriched_by"),
            "readiness": {"email": yn(em), "x": yn(rd.get("x_handle")), "linkedin": yn(rd.get("linkedin_url")),
                          "telegram": "yes" if rd.get("telegram") == "yes" else "no"}}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def build_shortlist_page(
    title: Annotated[str, Field(description="role title, e.g. 'Full-Stack Software Engineer'")],
    company: str,
    items: Annotated[list[dict[str, Any]], Field(description="items from match_job / match_job_text (with readiness)")],
    total: Annotated[int | None, Field(description="matches in the pool, for the header (e.g. match_job_text total)")] = None,
) -> dict[str, Any]:
    """Render a standalone HTML shortlist page (cards, filter chips, Keep/Skip, outreach preview; no email addresses)
    to /s/<slug> on talent.jubayerjuhan.site and return its URL."""
    import json
    if not items:
        raise ToolError("items is empty.")
    slug = _slug(company, title)
    talents = [_talent(i + 1, it) for i, it in enumerate(items)]
    from . import enrichment as _enr
    _found = _enr.lookup([x["id"] for x in talents if x["id"]])
    for x in talents:
        _hit = _found.get(x["id"])
        x["ai_enriched"] = _hit is not None
        if _hit:
            x["ai_enriched_by"] = _hit[1]
    safe = lambda o: json.dumps(o, ensure_ascii=False).replace("</", "<\\/")
    page = SHORTLIST_TEMPLATE.read_text(encoding="utf-8")
    for k, v in {"__TITLE__": title, "__COMPANY__": company, "__N__": str(len(talents)),
                 "__TOTAL__": f"{total:,}" if total else str(len(talents)),
                 "__DATE__": datetime.now(timezone.utc).strftime("%d %b %Y"),
                 "__COUNT_EMAIL__": str(sum(t["readiness"]["email"] == "yes" for t in talents)),
                 "__COUNT_X__": str(sum(t["readiness"]["x"] == "yes" for t in talents)),
                 "__COUNT_LI__": str(sum(t["readiness"]["linkedin"] == "yes" for t in talents)),
                 "__COUNT_TG__": str(sum(t["readiness"]["telegram"] == "yes" for t in talents))}.items():
        page = page.replace(k, html.escape(v))
    page = page.replace("__TALENTS__", safe(talents)).replace("__JOB__", safe({"title": title, "company": company}))
    page = EMAIL_RE.sub("[redacted]", page)
    (WWW / "s").mkdir(parents=True, exist_ok=True)
    (WWW / "s" / f"{slug}.html").write_text(page, encoding="utf-8")
    return {"url": SHORTLIST_BASE + slug, "slug": slug, "talents": len(talents)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
def export_csv(
    filename: Annotated[str, Field(description="file name for exports/, e.g. 'eth_p1.csv'")],
    cohort: list[Cohort] | None = None,
    activity: list[Literal["FULL_TIME", "PART_TIME", "ONE_TIME", "UNKNOWN"]] | None = None,
    tenure: list[Literal["ESTABLISHED", "EMERGING", "NEWCOMER", "UNKNOWN"]] | None = None,
    exclusivity: list[Literal["EXCLUSIVE", "MULTICHAIN", "UNKNOWN"]] | None = None,
    country: list[str] | None = None,
    chain: str | None = None,
    ecosystems: list[str] | None = None,
    ids: list[str] | None = None,
    hide_flagged: bool = True,
    ai_enriched: bool | None = None,
    text: str | None = None,
    sort: Sort = "active_days",
    direction: Literal["asc", "desc"] = "desc",
) -> dict[str, Any]:
    """Write up to 5,000 matching people (same filters as search_people) as CSV into exports/, like the viewer's export."""
    if not re.fullmatch(r"[\w.-]+\.csv", filename):
        raise ToolError("filename must be a plain name ending in .csv")
    q = people_filters(cohort, activity, tenure, exclusivity, country, chain, ecosystems, ids, hide_flagged, ai_enriched,
                       text, sort, direction)
    with db() as con:
        csv = queries.export_csv(con, q)
    EXPORTS.mkdir(exist_ok=True)
    path = EXPORTS / filename
    path.write_text(csv, encoding="utf-8-sig")
    return {"path": str(path), "rows": max(csv.count("\n") - 1, 0)}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def set_ai_enriched(
    person_ids: list[str],
    enriched_by: Annotated[str | None, Field(description="model or process that did the enrichment; required unless unset")] = None,
    unset: Annotated[bool, Field(description="true clears the flag instead")] = False,
) -> str:
    """Mark people as AI-enriched (or clear it). The viewer shows this as a badge and can filter on it."""
    bad = [i for i in person_ids if not PERSON_ID.fullmatch(i)]
    if bad or not person_ids:
        raise ToolError(f"Not person ids: {', '.join(bad[:5])}" if bad else "Give at least one person id.")
    if not unset and not enriched_by:
        raise ToolError("enriched_by is required: name the model or process that enriched them.")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = sqlite3.connect(ENRICHMENT)
    try:
        con.execute("PRAGMA journal_mode=WAL")  # the viewer reads while we write
        con.executescript(SCHEMA)
        con.executemany("INSERT OR REPLACE INTO ai_enrichment VALUES (?, ?, ?, ?)",
                        [(i, 0 if unset else 1, now, enriched_by) for i in person_ids])
        con.commit()
        total = con.execute("SELECT count(*) FROM ai_enrichment WHERE ai_enriched = 1").fetchone()[0]
    finally:
        con.close()
    return f"{'Cleared' if unset else 'Marked'} {len(person_ids)} people. AI-enriched now: {total}."


# Remote server: the same data over Streamable HTTP at /mcp on the viewer (viewer_api/main.py mounts it), for people
# who add it as a connector in claude.ai / Claude Desktop / Claude Code. The access gate checks the key (?key= on the
# connector URL, or X-Access-Key). Mostly read-only: no set_ai_enriched, and export_csv returns a download link instead
# of writing on this machine; the only writers are the two WRITE tools below.
remote = MCPServer("talent-seed", instructions=mcp.instructions)
for tool in (meta, overview, search_ecosystems, search_people, get_person, get_person_enrichment, get_github_profile,
             list_concepts, list_jobs, get_job, match_job, match_by_concepts, get_enrichment_batch):
    remote.add_tool(tool, annotations=READ)
# Writers: build_shortlist_page writes an HTML file to the web root, submit_enrichment writes client:-sourced evidence.
# Not exposed: match_job_text (needs the OpenAI key and stores jobs) and set_ai_enriched.
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
for tool in (build_shortlist_page, submit_enrichment):
    remote.add_tool(tool, annotations=WRITE)


@remote.tool(annotations=READ)
def export_csv_link(
    ctx: Context,
    cohort: list[Cohort] | None = None,
    activity: list[Literal["FULL_TIME", "PART_TIME", "ONE_TIME", "UNKNOWN"]] | None = None,
    tenure: list[Literal["ESTABLISHED", "EMERGING", "NEWCOMER", "UNKNOWN"]] | None = None,
    exclusivity: list[Literal["EXCLUSIVE", "MULTICHAIN", "UNKNOWN"]] | None = None,
    country: list[str] | None = None,
    chain: str | None = None,
    ecosystems: list[str] | None = None,
    ids: list[str] | None = None,
    hide_flagged: bool = True,
    ai_enriched: bool | None = None,
    text: str | None = None,
    sort: Sort = "active_days",
    direction: Literal["asc", "desc"] = "desc",
) -> dict[str, Any]:
    """Download link for up to 5,000 matching people as CSV (same filters as search_people). Give the link to the user."""
    q = people_filters(cohort, activity, tenure, exclusivity, country, chain, ecosystems, ids, hide_flagged, ai_enriched,
                       text, sort, direction)
    request = ctx.request_context.request
    params = {k: v[0] for k, v in q.items()}
    key = request.query_params.get("key") or request.headers.get("x-access-key")
    if key:
        params["key"] = key
    with db() as con:
        total = queries.api_people(con, {**q, "page": ["1"]}, 1)["total"]
    return {"url": f"{public_base(request)}/api/export.csv?{urlencode(params)}", "rows": min(total, EXPORT_LIMIT),
            "matches": total}


def public_base(request) -> str:
    """https://<tunnel host> as the user reaches it (cloudflared talks plain http to us on localhost)."""
    host = request.headers.get("host", "127.0.0.1:8765")
    scheme = "http" if host.startswith(("127.0.0.1", "localhost")) else "https"
    return f"{scheme}://{host}"


if __name__ == "__main__":
    mcp.run()
