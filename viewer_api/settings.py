"""Paths and settings shared by the API modules."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "talent_seed.duckdb"
LOGINS = ROOT / "data" / "github_logins.sqlite"
# The page served at "/". Until the React app replaces it (plan step 7), this is the current hand-written page.
INDEX = ROOT / "scripts" / "seed_viewer" / "index.html"
ACCESS_KEY = os.environ.get("TALENT_SEED_KEY", "")
KEY_COOKIE = "ts_key"
PAGE_SIZE = 50
EXPORT_LIMIT = 5000
ATTRIBUTION = "Data from Electric Capital Open Dev Data (opendevdata.org), CC BY 4.0"
