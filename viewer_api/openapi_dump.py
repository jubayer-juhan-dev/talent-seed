"""Print the API's OpenAPI schema (used by `pnpm gen:api` in web/ to generate TypeScript types)."""

import json

from viewer_api.main import app

print(json.dumps(app.openapi(), indent=2))
