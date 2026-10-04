"""Talent Seed viewer API: typed FastAPI endpoints over data/talent_seed.duckdb.

Run:   uv run uvicorn viewer_api.main:app --host 127.0.0.1 --port 8765
Docs:  /api/docs (needs the access key like everything else)

Read-only. Each request opens its own read-only DuckDB connection and closes it, so the database is
never locked between requests and scripts/m4_build_talent_seed.py can rebuild it (requests then get 503
until the build finishes). Same URLs and JSON as the old scripts/seed_viewer/server.py.
"""

from typing import Annotated

import duckdb
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import models, queries
from .auth import access_gate
from .settings import INDEX, WEB_DIST

app = FastAPI(title="Talent Seed viewer API", version="1.0", docs_url="/api/docs",
              openapi_url="/api/openapi.json", redoc_url=None)
app.middleware("http")(access_gate)


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


@app.get("/api/ecosystems", response_model=models.Ecosystems, response_model_exclude_unset=True, responses=ERRORS)
def ecosystems(con: Con, q: str = ""):
    return queries.jsonable(queries.api_ecosystems(con, {"q": [q]} if q else {}))


@app.get("/api/export.csv", response_class=Response, responses={**ERRORS, 200: {"content": {"text/csv": {}}}})
def export(con: Con, f: Annotated[Filters, Depends()]):
    """Up to 5,000 people as CSV, with the unverified-email, draft-cohort and attribution columns."""
    name = "talent_seed_shortlist.csv" if f.values["ids"] else "talent_seed_export.csv"
    return Response(queries.export_csv(con, f.q()).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def index():
    return FileResponse(INDEX, media_type="text/html; charset=utf-8")


@app.get("/next", include_in_schema=False)
def next_redirect(request: Request):
    return RedirectResponse(f"/next/{'?' + request.url.query if request.url.query else ''}")


@app.get("/next/{path:path}", include_in_schema=False)
def next_app(path: str):
    """The React app: real files from web/dist, anything else gets index.html (client-side routes)."""
    if not (WEB_DIST / "index.html").exists():
        raise HTTPException(404, "The new app isn't built yet (run `pnpm build` in web/).")
    f = (WEB_DIST / path).resolve()
    if path and f.is_file() and f.is_relative_to(WEB_DIST.resolve()):
        return FileResponse(f)
    return FileResponse(WEB_DIST / "index.html", media_type="text/html; charset=utf-8")

