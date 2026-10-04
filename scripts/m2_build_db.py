"""Milestone 2: build data/odd.duckdb from one raw snapshot.

- One VIEW per Parquet file (same name as the file stem), reading the immutable raw files.
- `_odd_lineage`: table -> snapshot id/date, source file, source URL, row count.
- `dev_identity_variants`: derived lookup table, one row per
  (canonical_developer_id, commit_author_email, commit_author_name) with first/last seen,
  commit counts and the latest commit SHA + repo. Built once so per-developer lookups don't
  re-scan the 22 GB commits file. Every row carries source_snapshot_id/date/tables.

Usage: uv run scripts/m2_build_db.py [snapshot_id] [--skip-derived]
"""

import json
import sys
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_open_dev_data"
DB = ROOT / "data" / "odd.duckdb"
# Git was first released 2005-04-07; anything earlier is a bogus author date.
MIN_VALID_AUTHORED_AT = "2005-04-01"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip_derived = "--skip-derived" in sys.argv
    snap_dir = RAW / args[0] if args else sorted(p for p in RAW.iterdir() if p.is_dir())[-1]
    meta = json.loads((snap_dir / "_snapshot_meta.json").read_text())
    snap_id, snap_date = meta["snapshot_id"], meta["snapshot_date"]

    DB.parent.mkdir(parents=True, exist_ok=True)
    tmp = ROOT / "data" / "duckdb_tmp"
    con = duckdb.connect(str(DB))
    con.execute(f"SET memory_limit='4GB'; SET temp_directory='{tmp}'; SET preserve_insertion_order=false; SET TimeZone='UTC';")

    con.execute("""CREATE OR REPLACE TABLE _odd_lineage (
        table_name VARCHAR PRIMARY KEY, source_snapshot_id VARCHAR, source_snapshot_date DATE,
        source_file VARCHAR, source_url VARCHAR, size_bytes BIGINT, b3sum VARCHAR, row_count BIGINT)""")
    for f in meta["files"]:
        table = f["file"].removesuffix(".parquet")
        path = (snap_dir / f["file"]).resolve()
        con.execute(f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM read_parquet('{path}')")
        rows = con.execute(f"SELECT sum(num_rows) FROM parquet_file_metadata('{path}')").fetchone()[0]
        con.execute("INSERT INTO _odd_lineage VALUES (?,?,?,?,?,?,?,?)",
                    [table, snap_id, snap_date, str(path), f["source_url"], f["size_bytes"], f["b3sum"], rows])
        print(f"view {table:48s} {rows:>15,}")

    if not skip_derived:
        t0 = time.time()
        print("building dev_identity_variants from commits (full scan) ...", flush=True)
        con.execute(f"""
        CREATE OR REPLACE TABLE dev_identity_variants AS
        SELECT
            canonical_developer_id,
            lower(trim(commit_author_email))                       AS email_norm,
            commit_author_email,
            commit_author_name,
            min(authored_at) FILTER (WHERE authored_at BETWEEN TIMESTAMPTZ '{MIN_VALID_AUTHORED_AT}'
                                     AND TIMESTAMPTZ '{snap_date}' + INTERVAL 1 DAY) AS first_seen_at,
            max(authored_at) FILTER (WHERE authored_at BETWEEN TIMESTAMPTZ '{MIN_VALID_AUTHORED_AT}'
                                     AND TIMESTAMPTZ '{snap_date}' + INTERVAL 1 DAY) AS last_seen_at,
            count(*)                                               AS n_commits,
            count(*) FILTER (WHERE authored_at NOT BETWEEN TIMESTAMPTZ '{MIN_VALID_AUTHORED_AT}'
                             AND TIMESTAMPTZ '{snap_date}' + INTERVAL 1 DAY) AS n_commits_bad_date,
            sum(is_bot)::BIGINT                                    AS n_bot_commits,
            count(DISTINCT repo_id)                                AS n_repos,
            arg_max(sha1, authored_at)                             AS latest_sha1,
            arg_max(repo_id, authored_at)                          AS latest_sha1_repo_id,
            '{snap_id}'                                            AS source_snapshot_id,
            DATE '{snap_date}'                                     AS source_snapshot_date,
            ['commits']                                            AS source_tables
        FROM commits
        GROUP BY ALL
        ORDER BY email_norm
        """)
        n = con.execute("SELECT count(*) FROM dev_identity_variants").fetchone()[0]
        print(f"dev_identity_variants: {n:,} rows in {time.time() - t0:.0f}s")
        con.execute("""INSERT OR REPLACE INTO _odd_lineage
            SELECT 'dev_identity_variants', ?, ?, 'derived: scripts/m2_build_db.py', NULL, NULL, NULL,
                   (SELECT count(*) FROM dev_identity_variants)""", [snap_id, snap_date])

    con.close()
    print(f"done: {DB}")


if __name__ == "__main__":
    main()
