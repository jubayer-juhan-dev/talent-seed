"""Milestone 1: fetch the ODD 'lite' file set (same list as `open-dev-data tui --lite`)
plus the two small developer-identity tables, verify blake3 against the manifest,
and load them into data/lite/odd_lite.duckdb as views over the Parquet files.

Downloaded Parquet files are treated as immutable: existing verified files are
skipped, never rewritten.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import blake3
import duckdb
import requests

MANIFEST_URL = "https://data.opendevdata.org/manifest.json"
BASE_URL = "https://data.opendevdata.org"
# Same list as open_dev_data.tui.LITE_FILES (v1.4)
LITE_FILES = ["eco_mads.parquet", "ecosystems_repos.parquet", "ecosystems.parquet", "repos.parquet"]
# Small extras needed to answer the developer-identity questions
EXTRA_FILES = ["canonical_developers.parquet", "canonical_developer_locations.parquet"]

ROOT = Path(__file__).resolve().parent.parent


def b3(path: Path) -> str:
    h = blake3.blake3()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    manifest = requests.get(MANIFEST_URL, timeout=60).json()
    version = manifest["dataset"]["version"]
    by_name = {r["path"].split("/")[-1]: r for r in manifest["dataset"]["resources"]}
    out_dir = ROOT / "data" / "lite" / version
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))

    files = []
    for name in LITE_FILES + EXTRA_FILES:
        res = by_name[name]
        url = res["path"] if res["path"].startswith("http") else BASE_URL + res["path"]
        dest = out_dir / name
        if dest.exists() and dest.stat().st_size == res["size_bytes"] and b3(dest) == res["b3sum"]:
            print(f"skip (verified) {name}")
        else:
            tmp = dest.with_suffix(".part")
            print(f"download {name} ({res['size_bytes'] / 1e6:.1f} MB)")
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 22):
                        f.write(chunk)
            if b3(tmp) != res["b3sum"]:
                tmp.unlink()
                sys.exit(f"blake3 mismatch for {name}")
            tmp.rename(dest)
            dest.chmod(0o444)
        files.append({"file": name, "size_bytes": res["size_bytes"], "b3sum": res["b3sum"], "url": url})

    (out_dir / "_snapshot_meta.json").write_text(json.dumps({
        "snapshot_id": version,
        "subset": "lite+canonical_developers",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "manifest_url": MANIFEST_URL,
        "files": files,
    }, indent=2))

    db_path = ROOT / "data" / "lite" / "odd_lite.duckdb"
    con = duckdb.connect(str(db_path))
    for f in files:
        table = f["file"].removesuffix(".parquet")
        con.execute(f"CREATE OR REPLACE VIEW {table} AS SELECT * FROM read_parquet('{out_dir / f['file']}')")
    con.close()
    print(f"views created in {db_path}")


if __name__ == "__main__":
    main()
