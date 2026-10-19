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
# Tier-1 GitHub harvest cache (viewer_api/github_profile.py). WAL-written while harvesting.
TIER1_GITHUB = ROOT / "data" / "tier1_github.sqlite"
# The React app (web/, `pnpm build`), served at /.
WEB_DIST = ROOT / "web" / "dist"
ACCESS_KEY = os.environ.get("TALENT_SEED_KEY", "")
KEY_COOKIE = "ts_key"
PAGE_SIZE = 50
EXPORT_LIMIT = 5000
ATTRIBUTION = "Data from Electric Capital Open Dev Data (opendevdata.org), CC BY 4.0"


def _neon_url():
    u = os.environ.get("DATABASE_URL", "")
    if not u:
        envf = ROOT / ".env"
        if envf.exists():
            for line in envf.read_text().splitlines():
                if line.startswith("DATABASE_URL="):
                    u = line.split("=", 1)[1].strip().strip('"').strip("'")
    return u


NEON_URL = _neon_url()
