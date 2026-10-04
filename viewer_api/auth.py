"""Access-key gate, same rules as the old server.

If TALENT_SEED_KEY is set, every request needs it as ?key=, an X-Access-Key header (the page sends it on
API calls) or the ts_key cookie (set when a page is opened with ?key=). The header path means the link
works in browsers that drop cookies. Without the key: 401. A stop-gap, not a real login.
"""

import hmac

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

from .settings import ACCESS_KEY, KEY_COOKIE

LOCKED_PAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Talent Seed</title><body style="font:15px system-ui;display:grid;place-items:center;min-height:90vh;color:#555">
<p>This page needs its access link. Ask the owner for the full URL.</p></body>"""
HEADERS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer"}


def _ok(value: str) -> bool:
    return bool(value) and hmac.compare_digest(value.encode(), ACCESS_KEY.encode())


async def access_gate(request: Request, call_next):
    if ACCESS_KEY and not any(_ok(v) for v in (request.query_params.get("key", ""), request.headers.get("x-access-key", ""),
                                              request.cookies.get(KEY_COOKIE, ""))):
        resp = (JSONResponse({"error": "Access link required"}, 401) if request.url.path.startswith("/api/")
                else HTMLResponse(LOCKED_PAGE, 401))
    else:
        resp = await call_next(request)
        # A page opened with ?key=: also set a cookie, so a later visit without the key still works.
        if ACCESS_KEY and _ok(request.query_params.get("key", "")) and not request.url.path.startswith("/api/"):
            resp.set_cookie(KEY_COOKIE, ACCESS_KEY, max_age=31536000, path="/", httponly=True, secure=True, samesite="lax")
    resp.headers.update(HEADERS)
    return resp
