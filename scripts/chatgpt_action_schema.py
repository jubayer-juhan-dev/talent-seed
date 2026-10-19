"""Print the OpenAPI schema to paste into a custom GPT's Action (ChatGPT → Create a GPT → Configure → Actions).

Run:   uv run scripts/chatgpt_action_schema.py > scratch/gpt_action.json

The viewer API's own schema, trimmed for ChatGPT: the current public tunnel URL as the server, short operation
names, and no CSV export (a GPT can't hand the file over). The key is not in here: the GPT sends it as the
X-Access-Key header (Authentication → API Key → Custom). Re-run and re-paste when the tunnel URL changes.
See docs/chatgpt_gpt.md.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from viewer_api.main import app  # noqa: E402
from viewer_api.settings import ROOT  # noqa: E402

OPERATIONS = {  # path -> operationId; anything else is left out
    "/api/meta": "getFilterValues",
    "/api/overview": "getOverview",
    "/api/ecosystems": "searchEcosystems",
    "/api/people": "searchPeople",
    "/api/person": "getPerson",
}

urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", (ROOT / "scratch" / "tunnel.log").read_text())
if not urls:
    sys.exit("No tunnel URL in scratch/tunnel.log. Is talent-seed-tunnel running?")

schema = app.openapi()
schema["info"] = {"title": "Talent Seed", "version": schema["info"]["version"],
                  "description": "Crypto developer talent data (Electric Capital Open Dev Data, CC BY 4.0)."}
schema["servers"] = [{"url": urls[-1]}]
schema["paths"] = {p: ops for p, ops in schema["paths"].items() if p in OPERATIONS}
for path, ops in schema["paths"].items():
    for op in ops.values():
        op["operationId"] = OPERATIONS[path]
        op.pop("tags", None)
json.dump(schema, sys.stdout, indent=2)
print()
