"""MCP server: lets Claude (Claude Code, Claude Desktop, …) use Talent Seed directly.

Run:   uv run python -m viewer_api.mcp_server          (stdio; Claude Code starts it from .mcp.json)

Same queries as the viewer API (viewer_api/queries.py), called in-process on a read-only DuckDB connection,
so no running viewer or access key is needed. The only write is set_ai_enriched, which writes
data/enrichment.sqlite the same way scripts/set_ai_enriched.py does.
"""

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

import duckdb
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import queries
from .enrichment import SCHEMA
from .settings import ENRICHMENT, ROOT

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
    return queries.jsonable(out)


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


if __name__ == "__main__":
    mcp.run()
