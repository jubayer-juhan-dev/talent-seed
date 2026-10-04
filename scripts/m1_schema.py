"""Milestone 1: dump schema + row count for every ODD table (footer-only reads for remote files)."""
import json
from pathlib import Path
import duckdb

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads(next((ROOT / "data/lite").glob("*/_manifest.json")).read_text())
version = manifest["dataset"]["version"]
local_dir = ROOT / "data/lite" / version
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
out = {}
for r in sorted(manifest["dataset"]["resources"], key=lambda r: r["path"]):
    name = r["path"].split("/")[-1]
    src = str(local_dir / name) if (local_dir / name).exists() else "https://data.opendevdata.org" + r["path"]
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{src}')").fetchall()
    rows = con.execute(f"SELECT sum(num_rows) FROM parquet_file_metadata('{src}')").fetchone()[0]
    out[name.removesuffix(".parquet")] = {"rows": rows, "local": src.startswith("/"), "columns": [[c[0], c[1]] for c in cols]}
    print(f"\n## {name}  rows={rows:,}  ({'local' if src.startswith('/') else 'remote'})")
    for c in cols:
        print(f"   {c[0]:40s} {c[1]}")
(ROOT / "scratch/schema.json").write_text(json.dumps(out, indent=2))
