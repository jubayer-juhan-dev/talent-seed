#!/usr/bin/env python3
"""Load the ProspectMind Talent Ontology seed into Postgres.

Reads `ontology_seed.yaml` (Skills Graph v0.4 seed) and applies it to the
Postgres schema in `ontology_schema.sql`:

    load order: families -> concepts (parents before children) -> relations
                -> concept_families

Derived relations:
  - IS_A      from each concept's `parent` field (v0.4 §5: specialized -> broader)
  - RELATED_TO from each concept's `related_concepts` list (symmetric pair)

Usage:
    python3 load_ontology.py --check            # validate YAML only, no output
    python3 load_ontology.py                    # validate + write load_ontology.sql
    python3 load_ontology.py --sql out.sql      # validate + write custom path
    psql "$DATABASE_URL" -f ontology_schema.sql -f load_ontology.sql

The SQL is idempotent (INSERT ... ON CONFLICT DO UPDATE), so re-running a
new seed version updates rows in place; concept IDs are never deleted per
v0.4 principles (merged/deprecated instead).
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent
SEED_DEFAULT = BASE / "ontology_seed.yaml"

TYPE_PREFIX = {
    "ROLE": "ROLE",
    "SKILL": "SKILL",
    "KNOWLEDGE": "KNOW",
    "CAPABILITY": "CAP",
    "TOOL": "TOOL",
    "SYSTEM": "SYS",
}
PREFIX_TYPE = {v: k for k, v in TYPE_PREFIX.items()}
ID_RE = re.compile(r"^PM\.(ROLE|SKILL|KNOW|CAP|TOOL|SYS)\.(\d{4})$")
RELATIONS = {"IS_A", "RELATED_TO", "USES", "APPLIES_TO", "ALIAS_OF"}
STATUSES = {"ACTIVE", "REVIEW_REQUIRED", "DEPRECATED", "MERGED"}


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def load_seed(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate(seed):
    errors = []

    families = seed.get("families", []) or []
    concepts = seed.get("concepts", []) or []
    relations = seed.get("relations", []) or []

    # --- families ---
    fam_ids = [f.get("id") for f in families]
    if len(set(fam_ids)) != len(fam_ids):
        errors.append("duplicate family ids")
    for f in families:
        if not f.get("id") or not f.get("name"):
            errors.append(f"family missing id/name: {f}")

    # --- concepts ---
    cids = [c.get("id") for c in concepts]
    if len(set(cids)) != len(cids):
        errors.append("duplicate concept ids")
    by_id = {}
    for c in concepts:
        cid, ctype = c.get("id"), c.get("type")
        m = ID_RE.match(cid or "")
        if not m:
            errors.append(f"concept id malformed: {cid}")
            continue
        if PREFIX_TYPE[m.group(1)] != ctype:
            errors.append(
                f"{cid}: id prefix {m.group(1)} does not match type {ctype}"
            )
        if not c.get("name"):
            errors.append(f"{cid}: missing name")
        if not c.get("definition"):
            errors.append(f"{cid}: missing definition")
        if c.get("status") and c["status"] not in STATUSES:
            errors.append(f"{cid}: bad status {c['status']}")
        parent = c.get("parent")
        if parent and parent not in cids:
            errors.append(f"{cid}: parent {parent} not found")
        if parent == cid:
            errors.append(f"{cid}: parent is itself")
        for f_ in c.get("families", []) or []:
            if f_ not in fam_ids:
                errors.append(f"{cid}: family {f_} not found")
        if not isinstance(c.get("aliases", []), list):
            errors.append(f"{cid}: aliases must be a list")
        if not isinstance(c.get("related_concepts", []), list):
            errors.append(f"{cid}: related_concepts must be a list")
        if not isinstance(c.get("evidence_rules", {}), dict):
            errors.append(f"{cid}: evidence_rules must be a mapping")
        if not isinstance(c.get("external_mappings", {}), dict):
            errors.append(f"{cid}: external_mappings must be a mapping")
        for r_ in c.get("related_concepts", []) or []:
            if r_ not in cids:
                errors.append(f"{cid}: related_concepts {r_} not found")
        by_id[cid] = c

    # IS_A acyclicity (from parent fields)
    visiting, seen = set(), set()

    def visit(cid):
        if cid in seen:
            return True
        if cid in visiting:
            return False
        visiting.add(cid)
        parent = by_id[cid].get("parent")
        if parent and not visit(parent):
            return False
        visiting.discard(cid)
        seen.add(cid)
        return True

    for cid in by_id:
        if not visit(cid):
            errors.append(f"IS_A cycle detected at {cid}")

    # --- relations ---
    for r in relations:
        s, rel, t = r.get("source"), r.get("relation"), r.get("target")
        if rel not in RELATIONS:
            errors.append(f"relation {s} {rel} {t}: unknown relation")
        if s not in by_id:
            errors.append(f"relation {s} {rel} {t}: source not found")
        if t not in by_id:
            errors.append(f"relation {s} {rel} {t}: target not found")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    return families, concepts, relations, by_id


def topo_concepts(concepts, by_id):
    """Parents before children (stable within seed order)."""
    order, seen = [], set()

    def visit(cid):
        if cid in seen:
            return
        parent = by_id[cid].get("parent")
        if parent:
            visit(parent)
        seen.add(cid)
        order.append(cid)

    for c in concepts:
        visit(c["id"])
    return [by_id[cid] for cid in order]


def sql_lit(v):
    return "'" + str(v).replace("'", "''") + "'"


def sql_array(items):
    return "ARRAY[" + ",".join(sql_lit(i) for i in items) + "]::text[]"


def sql_jsonb(obj):
    return sql_lit(json.dumps(obj or {}, ensure_ascii=False)) + "::jsonb"


def generate_sql(families, concepts, relations, by_id):
    lines = [
        "-- ProspectMind Talent Ontology — generated seed load",
        "-- Source: ontology_seed.yaml. Regenerate with load_ontology.py; do not edit by hand.",
        "-- Idempotent: safe to re-run on seed updates (updates rows in place).",
        "",
        "BEGIN;",
        "",
        "-- Families --------------------------------------------------------------",
    ]
    for f in families:
        lines.append(
            "INSERT INTO families (family_id, name, description) VALUES "
            f"({sql_lit(f['id'])}, {sql_lit(f['name'])}, {sql_lit(f['description'])}) "
            "ON CONFLICT (family_id) DO UPDATE SET name = EXCLUDED.name, "
            "description = EXCLUDED.description;"
        )
    lines += ["", "-- Concepts --------------------------------------------------------------"]
    for c in topo_concepts(concepts, by_id):
        cols = (
            "concept_id, concept_type, canonical_name, definition, parent_id, "
            "status, aliases, related_concepts, external_mappings, evidence_rules"
        )
        vals = ", ".join(
            [
                sql_lit(c["id"]),
                sql_lit(c["type"]),
                sql_lit(c["name"]),
                sql_lit(c["definition"]),
                sql_lit(c["parent"]) if c.get("parent") else "NULL",
                sql_lit(c.get("status") or "ACTIVE"),
                sql_array(c.get("aliases") or []),
                sql_array(c.get("related_concepts") or []),
                sql_jsonb(c.get("external_mappings")),
                sql_jsonb(c.get("evidence_rules")),
            ]
        )
        lines.append(
            f"INSERT INTO concepts ({cols}) VALUES ({vals}) "
            "ON CONFLICT (concept_id) DO UPDATE SET "
            "concept_type = EXCLUDED.concept_type, "
            "canonical_name = EXCLUDED.canonical_name, "
            "definition = EXCLUDED.definition, parent_id = EXCLUDED.parent_id, "
            "status = EXCLUDED.status, aliases = EXCLUDED.aliases, "
            "related_concepts = EXCLUDED.related_concepts, "
            "external_mappings = EXCLUDED.external_mappings, "
            "evidence_rules = EXCLUDED.evidence_rules, "
            "last_updated_date = CURRENT_DATE;"
        )
    lines += ["", "-- Relations -------------------------------------------------------------"]
    rel_rows = []
    # IS_A derived from parent fields
    for c in concepts:
        if c.get("parent"):
            rel_rows.append((c["id"], "IS_A", c["parent"]))
    # RELATED_TO pairs from related_concepts arrays (symmetric)
    for c in concepts:
        for r_ in c.get("related_concepts") or []:
            rel_rows.append((c["id"], "RELATED_TO", r_))
            rel_rows.append((r_, "RELATED_TO", c["id"]))
    # Explicit relations from the seed
    for r in relations:
        rel_rows.append((r["source"], r["relation"], r["target"]))
    for s, rel, t in sorted(set(rel_rows)):
        lines.append(
            "INSERT INTO concept_relations (source_id, relation, target_id) VALUES "
            f"({sql_lit(s)}, {sql_lit(rel)}, {sql_lit(t)}) ON CONFLICT DO NOTHING;"
        )
    lines += ["", "-- Concept ↔ family membership ------------------------------------------"]
    for c in concepts:
        for f_ in c.get("families") or []:
            lines.append(
                "INSERT INTO concept_families (concept_id, family_id) VALUES "
                f"({sql_lit(c['id'])}, {sql_lit(f_)}) ON CONFLICT DO NOTHING;"
            )
    lines += ["", "COMMIT;", ""]
    return "\n".join(lines), len(rel_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=str(SEED_DEFAULT))
    ap.add_argument("--check", action="store_true",
                    help="validate only, write nothing")
    ap.add_argument("--sql", default=None,
                    help="output path (default: load_ontology.sql next to seed)")
    args = ap.parse_args()

    seed = load_seed(args.seed)
    families, concepts, relations, by_id = validate(seed)

    n_concepts = len(concepts)
    n_families = len(families)
    n_explicit = len(relations)
    print(
        f"OK: {n_families} families, {n_concepts} concepts, "
        f"{n_explicit} explicit relations — all references resolve."
    )

    if args.check:
        return

    sql_text, n_rel = generate_sql(families, concepts, relations, by_id)
    out = Path(args.sql) if args.sql else BASE / "load_ontology.sql"
    out.write_text(sql_text, encoding="utf-8")
    print(f"Wrote {out} ({n_rel} relation rows after IS_A derivation).")


if __name__ == "__main__":
    main()
