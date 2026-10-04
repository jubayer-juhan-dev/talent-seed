"""Milestone 3 prep: add derived table `dev_github_ids` to data/odd.duckdb.

Decodes canonical_developers.primary_github_user_id (a GitHub GraphQL node ID) to the
numeric GitHub account ID, offline:
  legacy  'MDQ6VXNlcjE5NTA3NDgy' -> base64 -> '04:User19507482'
  new     'U_kgDOClp4rg'         -> base64url('kgDOClp4rg') -> msgpack [0, 173701294]
Bots use 'MDM6Qm90…' ('03:Bot…') / 'BOT_…'.

Then cross-checks the decoded IDs against the numeric IDs embedded in the developer's own
`<id>+<login>@users.noreply.github.com` commit emails, as a free validation of the decoding.
"""

import base64
import struct
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "odd.duckdb"


def decode_node_id(node_id: str | None) -> int | None:
    if not node_id:
        return None
    try:
        if node_id.startswith(("MDQ6", "MDM6")):  # legacy: base64("04:User123" / "03:Bot123")
            raw = base64.b64decode(node_id + "=" * (-len(node_id) % 4)).decode()
            digits = "".join(ch for ch in raw.split(":", 1)[1] if ch.isdigit())
            return int(digits) if digits else None
        prefix, _, payload = node_id.partition("_")
        if prefix not in ("U", "BOT") or not payload:
            return None
        b = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        # msgpack fixarray(2) [0, <uint>]
        if len(b) < 3 or b[0] != 0x92 or b[1] != 0x00:
            return None
        tag, rest = b[2], b[3:]
        if tag <= 0x7F:
            return tag
        fmt = {0xCC: ">B", 0xCD: ">H", 0xCE: ">I", 0xCF: ">Q"}.get(tag)
        return struct.unpack(fmt, rest[: struct.calcsize(fmt)])[0] if fmt else None
    except Exception:
        return None


def account_type(node_id: str | None) -> str | None:
    if not node_id:
        return None
    return "Bot" if node_id.startswith(("MDM6", "BOT_")) else "User"


def main() -> None:
    con = duckdb.connect(str(DB))
    snap_id, snap_date = con.execute(
        "SELECT source_snapshot_id, source_snapshot_date FROM _odd_lineage WHERE table_name='canonical_developers'"
    ).fetchone()
    # Decode in one Python pass (a per-row DuckDB Python UDF was far too slow), then load via CSV.
    rows = con.execute(
        "SELECT id, primary_github_user_id FROM canonical_developers WHERE primary_github_user_id IS NOT NULL"
    ).fetchall()
    tmp_csv = ROOT / "data" / "duckdb_tmp" / "dev_github_ids.csv"
    tmp_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_csv, "w") as f:
        f.write("canonical_developer_id,github_node_id,github_user_id,github_account_type\n")
        for dev_id, node_id in rows:
            gh_id = decode_node_id(node_id)
            f.write(f"{dev_id},{node_id},{'' if gh_id is None else gh_id},{account_type(node_id)}\n")
    con.execute(f"""
        CREATE OR REPLACE TABLE dev_github_ids AS
        SELECT canonical_developer_id::INTEGER AS canonical_developer_id,
               github_node_id::VARCHAR AS github_node_id,
               github_user_id::BIGINT AS github_user_id,
               github_account_type::VARCHAR AS github_account_type,
               '{snap_id}' AS source_snapshot_id,
               DATE '{snap_date}' AS source_snapshot_date,
               ['canonical_developers'] AS source_tables
        FROM read_csv('{tmp_csv}', header=true, all_varchar=true)
    """)
    tmp_csv.unlink()
    con.execute("""INSERT OR REPLACE INTO _odd_lineage
        SELECT 'dev_github_ids', ?, ?, 'derived: scripts/m3_build_github_ids.py', NULL, NULL, NULL,
               (SELECT count(*) FROM dev_github_ids)""", [snap_id, snap_date])

    print(con.sql("""SELECT github_account_type, count(*) AS n, count(github_user_id) AS decoded
                     FROM dev_github_ids GROUP BY 1 ORDER BY 2 DESC"""))
    # Validation against noreply emails of the same developer: '<id>+<login>@users.noreply.github.com'
    print(con.sql("""
        WITH nr AS (
            SELECT DISTINCT canonical_developer_id,
                   try_cast(regexp_extract(email_norm, '^([0-9]+)\\+[^@]+@users\\.noreply\\.github\\.com$', 1) AS BIGINT) AS nr_id
            FROM dev_identity_variants
            WHERE email_norm LIKE '%+%@users.noreply.github.com')
        SELECT count(*) AS pairs_compared,
               count(*) FILTER (WHERE nr.nr_id = g.github_user_id) AS id_matches,
               count(*) FILTER (WHERE nr.nr_id <> g.github_user_id) AS id_differs
        FROM nr JOIN dev_github_ids g USING (canonical_developer_id)
        WHERE nr.nr_id IS NOT NULL"""))
    con.close()


if __name__ == "__main__":
    main()
