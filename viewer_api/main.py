"""Talent Seed viewer API: typed FastAPI endpoints over data/talent_seed.duckdb.

Run:   uv run uvicorn viewer_api.main:app --host 127.0.0.1 --port 8765
Docs:  /api/docs (needs the access key like everything else)

Read-only. Each request opens its own read-only DuckDB connection and closes it, so the database is
never locked between requests and scripts/m4_build_talent_seed.py can rebuild it (requests then get 503
until the build finishes). Same URLs and JSON as the old scripts/seed_viewer/server.py.
"""

from contextlib import asynccontextmanager
from typing import Annotated

import duckdb
import sys
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel

from . import models, queries
from .auth import access_gate
from .mcp_server import remote
from .settings import WEB_DIST

# MCP for Claude at /mcp (viewer_api/mcp_server.py `remote`). Stateless JSON: no sessions to keep, nothing streamed.
# Host checks are off because the tunnel's host name changes; the access gate is what protects it.
mcp_app = remote.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, json_response=True,
                                     transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with remote.session_manager.run():
        yield


app = FastAPI(title="Talent Seed viewer API", version="1.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None, lifespan=lifespan)
app.middleware("http")(access_gate)


# Stateless server: no server-to-client stream to offer, and without this a GET (e.g. the URL opened in a browser)
# would sit on an empty event stream forever. Clients take 405 here as "POST only", as the MCP spec allows.
@app.get("/mcp", include_in_schema=False)
def mcp_get():
    return JSONResponse({"error": "This is the Talent Seed MCP endpoint for Claude. It doesn't open in a browser: add "
                                  "this URL (with ?key=...) as a custom connector in Claude instead."},
                        405, headers={"Allow": "POST"})


app.router.routes.extend(mcp_app.routes)  # added before the routes below, so ahead of the web app catch-all


# Errors keep the old {"error": "..."} shape, which the page shows to the user.
@app.exception_handler(HTTPException)
async def http_error(_req: Request, e: HTTPException):
    return JSONResponse({"error": str(e.detail)}, e.status_code)


@app.exception_handler(RequestValidationError)
async def bad_request(_req: Request, e: RequestValidationError):
    return JSONResponse({"error": "; ".join(f"{'.'.join(map(str, x['loc'][1:]))}: {x['msg']}" for x in e.errors())}, 422)


@app.exception_handler(Exception)
async def server_error(_req: Request, e: Exception):
    return JSONResponse({"error": f"{type(e).__name__}: {e}"}, 500)


def db():
    """One read-only connection per request, closed afterwards."""
    try:
        con = queries.connect()
    except duckdb.IOException:
        raise HTTPException(503, "The database is being rebuilt. Try again in a few minutes.")
    try:
        yield con
    finally:
        con.close()


Con = Annotated[duckdb.DuckDBPyConnection, Depends(db)]
ERRORS = {401: {"model": models.Error}, 503: {"model": models.Error}}


class Filters:
    """Query parameters shared by /api/people and /api/export.csv (same names as the old server)."""

    def __init__(
        self,
        cohort: Annotated[str, Query(description="P1,P2,P3,HOLD; comma-separated")] = "",
        activity: Annotated[str, Query(description="FULL_TIME,PART_TIME,ONE_TIME,UNKNOWN")] = "",
        tenure: Annotated[str, Query(description="ESTABLISHED,EMERGING,NEWCOMER,UNKNOWN")] = "",
        exclusivity: Annotated[str, Query(description="EXCLUSIVE,MULTICHAIN,UNKNOWN")] = "",
        country: Annotated[str, Query(description="comma-separated")] = "",
        chain: Annotated[str, Query(description="one top-level chain")] = "",
        eco: Annotated[str, Query(description="chains or projects, separated by |")] = "",
        ids: Annotated[str, Query(description="person ids (gh:… / odd:…), comma-separated")] = "",
        hide_flagged: Annotated[str, Query(description="1 hides probable bots and GitHub conflicts")] = "",
        ai_enriched: Annotated[str, Query(description="1 = AI-enriched only, 0 = not AI-enriched")] = "",
        q: Annotated[str, Query(description="name or login substring, exact email, or person id")] = "",
        sort: Annotated[str, Query(description=", ".join(queries.SORTS))] = "",
        dir: Annotated[str, Query(description="asc | desc")] = "",
    ):
        self.values = {k: v for k, v in locals().items() if k != "self"}

    def q(self, **extra) -> dict[str, list[str]]:
        """The parse_qs-style dict the query functions take."""
        return {k: [str(v)] for k, v in {**self.values, **extra}.items() if str(v)}


@app.get("/api/meta", response_model=models.Meta, response_model_exclude_unset=True, responses=ERRORS)
def meta(con: Con):
    return queries.jsonable(queries.api_meta(con, {}))


@app.get("/api/overview", response_model=models.Overview, response_model_exclude_unset=True, responses=ERRORS)
def overview(con: Con):
    return queries.jsonable(queries.api_overview(con, {}))


@app.get("/api/people", response_model=models.People, response_model_exclude_unset=True, responses=ERRORS)
def people(con: Con, f: Annotated[Filters, Depends()], page: Annotated[int, Query(ge=1)] = 1):
    return queries.jsonable(queries.api_people(con, f.q(page=page)))


@app.get("/api/person", response_model=models.PersonDetail, response_model_exclude_unset=True,
         responses={**ERRORS, 404: {"model": models.Error}})
def person(con: Con, person_id: Annotated[str, Query(alias="id", description="gh:… or odd:…")]):
    out = queries.api_person(con, {"id": [person_id]})
    if "error" in out:
        raise HTTPException(404, out["error"])
    return queries.jsonable(out)


@app.get("/api/person/enrichment", response_model=models.PersonEnrichment,
         responses={**ERRORS, 404: {"model": models.Error}})
def person_enrichment(person_id: Annotated[str, Query(alias="id", description="gh:... or odd:...")]):
    """AI enrichment for one person: LLM summary, inferred roles, evidence rows (Neon)."""
    from . import neon_enrichment
    out = neon_enrichment.fetch(person_id)
    if out is None:
        raise HTTPException(404, "no AI enrichment for this person")
    return out


@app.get("/api/person/github-profile", response_model=models.GithubProfile,
         responses={**ERRORS, 404: {"model": models.Error}})
def person_github_profile(person_id: Annotated[str, Query(alias="id", description="gh:... or odd:...")]):
    """GitHub profile details (website, X, LinkedIn, bio, ...) from the Tier-1 harvest cache."""
    from . import github_profile
    out = github_profile.fetch(person_id)
    if out is None:
        raise HTTPException(404, "GitHub profile not fetched yet for this person")
    return out


@app.get("/api/jobs", response_model=list[models.JobRow], responses=ERRORS)
def jobs_list():
    """Job Graph: all active jobs with requirement counts."""
    from . import jobs as jobmod
    out = []
    for j in jobmod.list_jobs():
        j = dict(j)
        j["requirements_count"] = j.pop("count", 0) if "count" in j else 0
        out.append(j)
    return out


@app.get("/api/jobs/{job_id}", response_model=models.JobDetail,
         responses={**ERRORS, 404: {"model": models.Error}})
def job_detail(job_id: str):
    from . import jobs as jobmod
    out = jobmod.get_job(job_id)
    if out is None:
        raise HTTPException(404, "job not found")
    return out


@app.get("/api/jobs/{job_id}/matches", response_model=models.JobMatches,
         responses={**ERRORS, 404: {"model": models.Error}})
def job_matches(job_id: str, con: Con, pool: str = "all", limit: int = 50):
    """j3 matching: ranked talents with per-concept evidence breakdown."""
    from . import jobs as jobmod
    if jobmod.get_job(job_id) is None:
        raise HTTPException(404, "job not found")
    out = jobmod.match(job_id, pool=pool, limit=limit)
    for r in out["items"]:
        row = con.execute(
            "SELECT display_name, github_login FROM talent_seed WHERE person_id = ?",
            [r["talent_id"]]).fetchone()
        if row:
            r["name"], r["github_login"] = row[0], row[1]
    return out


class JobRequirementEdit(BaseModel):
    concept_id: str | None = None
    concept_name: str
    concept_type: str = "SKILL"
    requirement: str = "required"


@app.patch("/api/jobs/{job_id}/requirements", response_model=models.JobDetail,
           responses={**ERRORS, 404: {"model": models.Error}})
def job_edit_requirements(job_id: str, body: list[JobRequirementEdit]):
    """Recruiter correction: replace the extracted requirement set (optional step)."""
    import os
    import psycopg2
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM jobs WHERE job_id = %s", (job_id,))
        if not cur.fetchone():
            raise HTTPException(404, "job not found")
        cur.execute("SELECT concept_id, canonical_name FROM concepts")
        known = {name: cid for cid, name in cur.fetchall()}
        cur.execute("DELETE FROM job_requirements WHERE job_id = %s", (job_id,))
        for r in body:
            cur.execute(
                "INSERT INTO job_requirements (job_id, concept_id, concept_name,"
                " concept_type, requirement, status, confidence, evidence_text, source)"
                " VALUES (%s,%s,%s,%s,%s,'FACT',1.0,'recruiter edit','manual:edit')"
                " ON CONFLICT DO NOTHING",
                (job_id, known.get(r.concept_name, r.concept_id), r.concept_name,
                 r.concept_type,
                 r.requirement if r.requirement in ("required", "nice_to_have")
                 else "required"))
    finally:
        conn.close()
    from . import jobs as jobmod
    return jobmod.get_job(job_id)


@app.post("/api/jobs", response_model=models.JobDetail, responses=ERRORS)
def job_create(body: models.JobCreate):
    """Paste a job -> j2 extraction -> stored job with requirements."""
    import os
    import psycopg2
    from openai import OpenAI
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.j2_extract_job import extract_job
    from . import jobs as jobmod
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    try:
        job_id, _rows, _out = extract_job(
            conn.cursor(), OpenAI(), "gpt-6-luna", body.title, body.company,
            body.location, body.description, "manual", None)
    finally:
        conn.close()
    return jobmod.get_job(job_id)


@app.get("/api/ecosystems", response_model=models.Ecosystems, response_model_exclude_unset=True, responses=ERRORS)
def ecosystems(con: Con, q: str = ""):
    return queries.jsonable(queries.api_ecosystems(con, {"q": [q]} if q else {}))


@app.get("/api/export.csv", response_class=Response, responses={**ERRORS, 200: {"content": {"text/csv": {}}}})
def export(con: Con, f: Annotated[Filters, Depends()]):
    """Up to 5,000 people as CSV, with the unverified-email, draft-cohort and attribution columns."""
    name = "talent_seed_shortlist.csv" if f.values["ids"] else "talent_seed_export.csv"
    return Response(queries.export_csv(con, f.q()).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/next", include_in_schema=False)
@app.get("/next/{path:path}", include_in_schema=False)
def next_redirect(request: Request, path: str = ""):
    """The React app was previewed at /next/ before the switch-over; send those links to the same page at /."""
    return RedirectResponse(f"/{path}{'?' + request.url.query if request.url.query else ''}", status_code=301)


@app.get("/{path:path}", include_in_schema=False)
def web_app(path: str):
    """The React app: real files from web/dist, anything else gets index.html (client-side routes like /explore)."""
    if path.startswith("api/"):
        raise HTTPException(404, "not found")
    if not (WEB_DIST / "index.html").exists():
        raise HTTPException(503, "The app isn't built yet (run `pnpm build` in web/).")
    f = (WEB_DIST / path).resolve()
    if path and f.is_file() and f.is_relative_to(WEB_DIST.resolve()):
        return FileResponse(f)
    return FileResponse(WEB_DIST / "index.html", media_type="text/html; charset=utf-8")
