-- ============================================================================
-- ProspectMind — Talent Ontology schema, v0.1
-- Derived from: "ProspectMind Talent — Skills Graph" v0.4
--   §4  Canonical concepts (fields preserved 1:1)
--   §5  Relations between concepts
--   §12 Persistence (evidence objects)
-- Principles applied: stable Concept_IDs (never reused, never deleted — merged or
--   deprecated instead); aliases normalize, never fork; IS_A is acyclic;
--   evidence is preserved before scores; graph DB optional (tables carry v1).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Concepts: the shared canonical vocabulary.
-- concept_type: ROLE | SKILL | KNOWLEDGE | CAPABILITY | TOOL | SYSTEM
--   (Industry is OPEN per v0.4 §4 — do not invent it here.)
-- status: ACTIVE | REVIEW_REQUIRED | DEPRECATED | MERGED
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS concepts (
  concept_id        TEXT PRIMARY KEY,   -- e.g. 'PM.SKILL.0003' — stable forever
  concept_type      TEXT NOT NULL
                      CHECK (concept_type IN
                        ('ROLE','SKILL','KNOWLEDGE','CAPABILITY','TOOL','SYSTEM')),
  canonical_name    TEXT NOT NULL,
  definition        TEXT NOT NULL,
  parent_id         TEXT REFERENCES concepts(concept_id),
  status            TEXT NOT NULL DEFAULT 'ACTIVE'
                      CHECK (status IN
                        ('ACTIVE','REVIEW_REQUIRED','DEPRECATED','MERGED')),
  aliases           TEXT[]  NOT NULL DEFAULT '{}',
  related_concepts  TEXT[]  NOT NULL DEFAULT '{}',  -- symmetric RELATED_TO ids
  external_mappings JSONB   NOT NULL DEFAULT '{}',   -- {"esco":"...","wikidata":"..."}
  evidence_rules    JSONB   NOT NULL DEFAULT '{}',   -- per-level rules, see seed
  created_date      DATE    NOT NULL DEFAULT CURRENT_DATE,
  last_updated_date DATE    NOT NULL DEFAULT CURRENT_DATE
);
CREATE INDEX IF NOT EXISTS idx_concepts_type   ON concepts(concept_type);
CREATE INDEX IF NOT EXISTS idx_concepts_parent ON concepts(parent_id);
CREATE INDEX IF NOT EXISTS idx_concepts_status ON concepts(status);

-- ----------------------------------------------------------------------------
-- Relations between concepts (§5). Direction matters; see seed for examples.
-- IS_A: specialized → broader, same type, acyclic.
-- RELATED_TO: symmetric, no automatic equivalence.
-- USES: capability → tool/technology (association, not attribution).
-- APPLIES_TO: capability → domain/system (application context).
-- ALIAS_OF: label → concept (normalization only).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS concept_relations (
  source_id TEXT NOT NULL REFERENCES concepts(concept_id),
  relation  TEXT NOT NULL
              CHECK (relation IN
                ('IS_A','RELATED_TO','USES','APPLIES_TO','ALIAS_OF')),
  target_id TEXT NOT NULL REFERENCES concepts(concept_id),
  PRIMARY KEY (source_id, relation, target_id)
);

-- ----------------------------------------------------------------------------
-- Families: navigation only (§7.1). A family is NOT a skill; multi-membership
-- allowed via concept_families without changing parent_id.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS families (
  family_id   TEXT PRIMARY KEY,   -- e.g. 'FAM.WEB3'
  name        TEXT NOT NULL,
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS concept_families (
  concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
  family_id  TEXT NOT NULL REFERENCES families(family_id),
  PRIMARY KEY (concept_id, family_id)
);

-- ----------------------------------------------------------------------------
-- Evidence objects (§12). Components are analyzed once (revision pinned);
-- usage evidence records the observation, never the conclusion.
-- usage_level: DECLARED | OBSERVED_USAGE | CONTRIBUTOR_USAGE | ADVANCED_USAGE
-- status: FACT | INFERENCE | UNKNOWN
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS code_components (
  component_id  TEXT PRIMARY KEY,
  repository_id TEXT NOT NULL,        -- Talent Graph Repository_ID
  revision      TEXT NOT NULL,        -- analyzed commit SHA
  path          TEXT NOT NULL,
  languages     TEXT[] NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS library_usage_evidence (
  evidence_id      TEXT PRIMARY KEY,
  talent_id        TEXT NOT NULL,      -- Talent Seed person id
  component_id     TEXT REFERENCES code_components(component_id),
  package_ecosystem TEXT NOT NULL,     -- npm | crates | pypi | go | …
  package_name     TEXT NOT NULL,      -- normalized; purl where available
  usage_level      TEXT NOT NULL
                     CHECK (usage_level IN
                       ('DECLARED','OBSERVED_USAGE',
                        'CONTRIBUTOR_USAGE','ADVANCED_USAGE')),
  evidence_url     TEXT NOT NULL,
  observed_date    DATE NOT NULL,
  first_observed   DATE,
  last_observed    DATE,
  confidence       NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
  status           TEXT NOT NULL DEFAULT 'FACT'
                     CHECK (status IN ('FACT','INFERENCE','UNKNOWN'))
);
CREATE INDEX IF NOT EXISTS idx_evidence_talent ON library_usage_evidence(talent_id);
