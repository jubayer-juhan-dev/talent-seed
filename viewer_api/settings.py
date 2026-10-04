"""Paths and settings shared by the API modules."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "talent_seed.duckdb"
LOGINS = ROOT / "data" / "github_logins.sqlite"
# Per-person AI-enrichment flag (viewer_api/enrichment.py, scripts/set_ai_enriched.py).
ENRICHMENT = ROOT / "data" / "enrichment.sqlite"
# DuckDB extensions (sqlite reader). Explicit, because the systemd service has no home directory.
DUCKDB_EXTENSIONS = ROOT / "data" / "duckdb_extensions"
# The page served at "/". Until the React app replaces it (plan step 7), this is the current hand-written page.
INDEX = ROOT / "scripts" / "seed_viewer" / "index.html"
# The React app (web/, `pnpm build`), previewed at /next/ until the switch-over.
WEB_DIST = ROOT / "web" / "dist"
ACCESS_KEY = os.environ.get("TALENT_SEED_KEY", "")
KEY_COOKIE = "ts_key"
PAGE_SIZE = 50
EXPORT_LIMIT = 5000
ATTRIBUTION = "Data from Electric Capital Open Dev Data (opendevdata.org), CC BY 4.0"
