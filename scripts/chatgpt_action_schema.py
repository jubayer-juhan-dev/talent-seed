"""Print the OpenAPI schema to paste into a custom GPT's Action (ChatGPT → Create a GPT → Configure → Actions).

Run:   uv run scripts/chatgpt_action_schema.py > scratch/gpt_action.json

The viewer API's own schema, trimmed for ChatGPT: the public domain as the server, short operation names, read-only
(GET) operations only, and no CSV export (a GPT can't hand the file over). The key is not in here: the GPT sends it
as the X-Access-Key header (Authentication → API Key → Custom). Re-run and re-paste when the API gains endpoints.
See docs/chatgpt_gpt.md.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from viewer_api.main import app  # noqa: E402

SERVER = "https://talent.jubayerjuhan.site"
OPERATIONS = {  # path -> operationId for its GET; anything else (and every write) is left out
    "/api/meta": "getFilterValues",
    "/api/overview": "getOverview",
    "/api/ecosystems": "searchEcosystems",
    "/api/people": "searchPeople",
    "/api/person": "getPerson",
    "/api/person/enrichment": "getPersonEnrichment",
    "/api/person/github-profile": "getGithubProfile",
    "/api/concepts": "listConcepts",
    "/api/jobs": "listJobs",
    "/api/jobs/{job_id}": "getJob",
    "/api/jobs/{job_id}/matches": "matchJob",
}

schema = app.openapi()
schema["info"] = {"title": "Talent Seed", "version": schema["info"]["version"],
                  "description": "Crypto developer talent data (Electric Capital Open Dev Data, CC BY 4.0)."}
schema["servers"] = [{"url": SERVER}]
schema["paths"] = {p: {"get": ops["get"]} for p, ops in schema["paths"].items() if p in OPERATIONS}
for path, ops in schema["paths"].items():
    ops["get"]["operationId"] = OPERATIONS[path]
    ops["get"].pop("tags", None)
json.dump(schema, sys.stdout, indent=2)
print()
