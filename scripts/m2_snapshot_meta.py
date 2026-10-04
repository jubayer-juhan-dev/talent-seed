"""Milestone 2: write raw_open_dev_data/<snapshot>/_snapshot_meta.json for a downloaded snapshot.

Verifies every manifest file is present with the expected size (the downloader already
checked blake3), marks the Parquet files read-only, and records provenance.

Usage: uv run scripts/m2_snapshot_meta.py [snapshot_id]   (default: the only/latest folder)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_open_dev_data"
MANIFEST_URL = "https://data.opendevdata.org/manifest.json"
BASE_URL = "https://data.opendevdata.org"


def main() -> None:
    snap_dir = RAW / sys.argv[1] if len(sys.argv) > 1 else sorted(p for p in RAW.iterdir() if p.is_dir())[-1]
    snapshot_id = snap_dir.name

    # Manifest is replaced daily; prefer the copy saved when this snapshot was current.
    saved = ROOT / "data/lite" / snapshot_id / "_manifest.json"
    manifest = json.loads(saved.read_text()) if saved.exists() else requests.get(MANIFEST_URL, timeout=60).json()
    if manifest["dataset"]["version"] != snapshot_id:
        sys.exit(f"live manifest is {manifest['dataset']['version']}, folder is {snapshot_id}; "
                 "cannot attest file list from a different manifest")

    started = (ROOT / "scratch/download_started_at").read_text().strip()
    files, problems = [], []
    for r in manifest["dataset"]["resources"]:
        name = Path(r["path"]).name
        p = snap_dir / name
        size = p.stat().st_size if p.exists() else None
        if size != r["size_bytes"]:
            problems.append(f"{name}: expected {r['size_bytes']}, got {size}")
            continue
        p.chmod(0o444)
        files.append({
            "file": name,
            "size_bytes": size,
            "b3sum": r["b3sum"],
            "source_url": BASE_URL + r["path"] if not r["path"].startswith("http") else r["path"],
            "description": r.get("description"),
        })
    if problems or list(snap_dir.glob("*.tmp")):
        sys.exit("incomplete snapshot:\n" + "\n".join(problems))

    meta = {
        "snapshot_id": snapshot_id,
        "snapshot_date": f"{snapshot_id[:4]}-{snapshot_id[4:6]}-{snapshot_id[6:8]}",
        "manifest_created": manifest["dataset"].get("created"),
        "download_started_at": started,
        "download_completed_at": datetime.fromtimestamp(
            max((snap_dir / f["file"]).stat().st_mtime for f in files), timezone.utc).isoformat(),
        "meta_written_at": datetime.now(timezone.utc).isoformat(),
        "downloader": "open-dev-data 1.4 via scripts/odd_cli.py (aiohttp socket_options shim); blake3 verified by downloader",
        "manifest_url": MANIFEST_URL,
        "publisher": manifest["dataset"].get("publisher"),
        "license": manifest["dataset"].get("license"),
        "attribution": "Data from Electric Capital Open Dev Data (https://opendevdata.org), licensed CC BY 4.0.",
        "total_size_bytes": sum(f["size_bytes"] for f in files),
        "files": files,
    }
    out = snap_dir / "_snapshot_meta.json"
    out.write_text(json.dumps(meta, indent=2))
    out.chmod(0o444)
    (snap_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {out}: {len(files)} files, {meta['total_size_bytes'] / 1e9:.2f} GB")


if __name__ == "__main__":
    main()
