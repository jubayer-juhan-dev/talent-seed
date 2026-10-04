"""Mark people as AI-enriched (or clear the flag) in data/enrichment.sqlite.

The viewer shows the flag as a badge on rows and profiles, filters on it, and exports it. An AI enrichment
job should call this (or write the same table) after it enriches someone.

  uv run scripts/set_ai_enriched.py --by "claude-opus-5-5" gh:19890894 gh:1076145
  uv run scripts/set_ai_enriched.py --by "enrich-job v2" --file ids.txt     # one person_id per line
  uv run scripts/set_ai_enriched.py --unset gh:19890894
  uv run scripts/set_ai_enriched.py --list
"""

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from viewer_api.enrichment import SCHEMA  # noqa: E402
from viewer_api.settings import ENRICHMENT  # noqa: E402

PERSON_ID = re.compile(r"(gh|odd):\d+")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", help="person ids (gh:… / odd:…)")
    ap.add_argument("--file", help="file with one person id per line")
    ap.add_argument("--by", help="model or process that did the enrichment (required when setting)")
    ap.add_argument("--unset", action="store_true", help="mark as not AI-enriched")
    ap.add_argument("--list", action="store_true", help="print who is AI-enriched")
    a = ap.parse_args()

    db = sqlite3.connect(ENRICHMENT)
    db.execute("PRAGMA journal_mode=WAL")  # the viewer reads while we write
    db.executescript(SCHEMA)

    if a.list:
        for row in db.execute("SELECT person_id, enriched_at, enriched_by FROM ai_enrichment WHERE ai_enriched = 1 ORDER BY enriched_at"):
            print(*row, sep="\t")
        return

    ids = list(a.ids)
    if a.file:
        ids += [line.strip() for line in Path(a.file).read_text().splitlines() if line.strip()]
    bad = [i for i in ids if not PERSON_ID.fullmatch(i)]
    if bad:
        sys.exit(f"Not person ids: {', '.join(bad[:5])}")
    if not ids:
        sys.exit("Give person ids or --file (see --help).")
    if not a.unset and not a.by:
        sys.exit("--by is required: name the model or process that enriched them.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.executemany("INSERT OR REPLACE INTO ai_enrichment VALUES (?, ?, ?, ?)",
                   [(i, 0 if a.unset else 1, now, a.by) for i in ids])
    db.commit()
    total = db.execute("SELECT count(*) FROM ai_enrichment WHERE ai_enriched = 1").fetchone()[0]
    print(f"{'Cleared' if a.unset else 'Marked'} {len(ids)} people. AI-enriched now: {total}.")


if __name__ == "__main__":
    main()
