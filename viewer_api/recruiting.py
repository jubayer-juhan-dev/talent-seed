"""Recruiting / availability enrichment: is this person realistically recruitable?

Append-only provenance store in data/enrichment.sqlite. Every field value is a row with its
level (FACT = publicly observed signal, INFERENCE = judged from evidence), source, evidence
text, confidence, observation date and author — history is never overwritten, the current
value of a field is simply its newest row. Estimated salary is an INFERENCE by construction:
it is only stored as a FACT when the source is the person's own direct statement.

Writers: deterministic extraction from the tier-1 GitHub cache (company, hireable flag,
location, public-activity floor for experience) and client AI submissions through the MCP.
The offer-acceptability scorer is deterministic and job-specific; it is computed on demand
and never stored as a permanent score.
"""

import json
import re
import sqlite3
from datetime import date, datetime, timezone

from .settings import ENRICHMENT, TIER1_GITHUB

SCHEMA = """
CREATE TABLE IF NOT EXISTS recruiting_fields (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id     TEXT NOT NULL,
    field         TEXT NOT NULL,
    value         TEXT NOT NULL,
    level         TEXT NOT NULL CHECK (level IN ('FACT', 'INFERENCE')),
    source_type   TEXT,
    source_url    TEXT,
    evidence_text TEXT,
    confidence    REAL,
    observed_at   TEXT NOT NULL,
    enriched_at   TEXT NOT NULL,
    enriched_by   TEXT
);
CREATE INDEX IF NOT EXISTS idx_rf_person_field ON recruiting_fields(person_id, field, id);
"""

ENUMS = {
    "open_to_work_status": ("YES", "LIKELY", "UNKNOWN", "NO"),
    "employment_status": ("EMPLOYED", "FREELANCE", "BETWEEN_JOBS", "STUDENT", "FOUNDER", "UNKNOWN"),
    "seniority_level": ("JUNIOR", "MID", "SENIOR", "STAFF", "PRINCIPAL", "LEAD", "MANAGER", "EXECUTIVE", "UNKNOWN"),
    "hands_on_engineering": ("YES", "PARTIAL", "NO", "UNKNOWN"),
    "remote_preference": ("REMOTE", "HYBRID", "ONSITE", "FLEXIBLE", "UNKNOWN"),
    "relocation_openness": ("YES", "LIKELY", "UNKNOWN", "NO"),
}
TEXT_FIELDS = ("current_company", "current_title", "current_city", "current_country")
DATE_FIELDS = ("current_role_start_date", "last_job_change_date")
NUMBER_FIELDS = ("estimated_years_experience",)
LIST_FIELDS = ("relocation_locations", "work_authorization_countries", "career_signals")
OBJECT_FIELDS = ("estimated_current_salary", "expected_salary")
ALL_FIELDS = tuple(ENUMS) + TEXT_FIELDS + DATE_FIELDS + NUMBER_FIELDS + LIST_FIELDS + OBJECT_FIELDS

SIGNAL_TYPES = ("recent_layoff_signal", "recent_contract_end_signal", "freelance_availability_signal",
                "recent_company_exit_signal", "recent_profile_update_signal", "recent_job_search_signal")

GROUPS = {
    "availability": ("open_to_work_status",),
    "employment": ("employment_status", "current_company", "current_title", "current_role_start_date",
                   "last_job_change_date"),
    "seniority": ("estimated_years_experience", "seniority_level", "hands_on_engineering"),
    "compensation": ("estimated_current_salary", "expected_salary"),
    "location": ("current_city", "current_country", "remote_preference", "relocation_openness",
                 "relocation_locations", "work_authorization_countries"),
    "signals": ("career_signals",),
}


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_entry(e: dict) -> dict:
    """Validate one field entry; returns it normalised. Raises ValueError with the reason."""
    field = e.get("field")
    if field not in ALL_FIELDS:
        raise ValueError(f"Unknown field: {field!r}. Allowed: {', '.join(ALL_FIELDS)}")
    if "value" not in e or e["value"] is None:
        raise ValueError(f"{field}: value is required")
    value = e["value"]
    level = str(e.get("level") or "").upper()
    if level not in ("FACT", "INFERENCE"):
        raise ValueError(f"{field}: level must be FACT or INFERENCE")
    evidence = (e.get("evidence_text") or "").strip()
    if len(evidence) < 3:
        raise ValueError(f"{field}: evidence_text is required — no value without its evidence")
    source_type = (e.get("source_type") or "").strip()
    if not source_type:
        raise ValueError(f"{field}: source_type is required")
    confidence = e.get("confidence")
    if level == "INFERENCE":
        if confidence is None:
            raise ValueError(f"{field}: INFERENCE requires a confidence between 0 and 1")
        confidence = float(confidence)
        if not 0 <= confidence <= 1:
            raise ValueError(f"{field}: confidence must be between 0 and 1")
    if field in ENUMS:
        value = str(value).upper()
        if value not in ENUMS[field]:
            raise ValueError(f"{field}: must be one of {', '.join(ENUMS[field])}")
    elif field in TEXT_FIELDS:
        value = " ".join(str(value).split())[:200]
        if not value:
            raise ValueError(f"{field}: empty value")
    elif field in DATE_FIELDS:
        value = str(value).strip()
        if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", value):
            raise ValueError(f"{field}: date must be YYYY, YYYY-MM or YYYY-MM-DD")
    elif field in NUMBER_FIELDS:
        value = float(value)
        if not 0 <= value <= 60:
            raise ValueError(f"{field}: years of experience must be between 0 and 60")
    elif field in LIST_FIELDS:
        if not isinstance(value, list):
            raise ValueError(f"{field}: value must be a list")
        if field == "career_signals":
            for s in value:
                if not isinstance(s, dict) or s.get("type") not in SIGNAL_TYPES:
                    raise ValueError(f"career_signals: each signal needs a type in {', '.join(SIGNAL_TYPES)}")
                if not s.get("date") or not s.get("evidence"):
                    raise ValueError("career_signals: each signal needs a date and evidence")
    elif field in OBJECT_FIELDS:
        if not isinstance(value, dict):
            raise ValueError(f"{field}: value must be an object {{min, max, currency, ...}}")
        for k in ("min", "max", "currency"):
            if value.get(k) is None:
                raise ValueError(f"{field}: object needs min, max and currency")
        if field == "estimated_current_salary":
            if not value.get("basis"):
                raise ValueError("estimated_current_salary: basis is required — how was this estimated?")
            if value.get("confidence") is None:
                raise ValueError("estimated_current_salary: confidence is required inside the estimate")
            # An estimate is an inference by construction, unless the person stated it directly.
            if source_type != "direct_statement":
                level = "INFERENCE"
    observed = str(e.get("observed_at") or _today()).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", observed):
        raise ValueError(f"{field}: observed_at must be a date (YYYY-MM-DD)")
    return {"field": field, "value": value, "level": level, "source_type": source_type,
            "source_url": (e.get("source_url") or None), "evidence_text": evidence[:600],
            "confidence": confidence, "observed_at": observed[:10]}


def _connect():
    db = sqlite3.connect(ENRICHMENT)
    db.executescript(SCHEMA)
    return db


def submit(person_id: str, entries: list[dict], enriched_by: str | None) -> dict:
    """Append validated entries as new provenance rows. Nothing is overwritten; history grows."""
    clean = [validate_entry(e) for e in entries]
    now = _now()
    db = _connect()
    try:
        db.executemany(
            "INSERT INTO recruiting_fields (person_id, field, value, level, source_type, source_url, "
            "evidence_text, confidence, observed_at, enriched_at, enriched_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(person_id, c["field"], json.dumps(c["value"]), c["level"], c["source_type"], c["source_url"],
              c["evidence_text"], c["confidence"], c["observed_at"], now, enriched_by) for c in clean])
        db.commit()
    finally:
        db.close()
    return {"person_id": person_id, "stored": len(clean), "fields": [c["field"] for c in clean]}


def current(person_ids) -> dict:
    """{person_id: {field: {value, level, source_type, source_url, evidence_text, confidence, observed_at, enriched_by}}} — newest row per field."""
    ids = [p for p in dict.fromkeys(person_ids) if p]
    if not ids or not ENRICHMENT.exists():
        return {}
    db = sqlite3.connect(f"file:{ENRICHMENT}?mode=ro", uri=True)
    try:
        out = {}
        for i in range(0, len(ids), 900):
            chunk = ids[i:i + 900]
            try:
                rows = db.execute(
                    f"SELECT person_id, field, value, level, source_type, source_url, evidence_text, confidence, "
                    f"observed_at, enriched_by FROM recruiting_fields WHERE person_id IN ({','.join('?' * len(chunk))}) "
                    f"ORDER BY id", chunk).fetchall()
            except sqlite3.OperationalError:
                return {}
            for pid, field, value, level, st, surl, ev, conf, obs, by in rows:
                out.setdefault(pid, {})[field] = {
                    "value": json.loads(value), "level": level, "source_type": st, "source_url": surl,
                    "evidence_text": ev, "confidence": conf, "observed_at": obs, "enriched_by": by}
        return out
    finally:
        db.close()


def _months_since(d: str | None) -> int | None:
    if not d:
        return None
    try:
        parts = [int(x) for x in d.split("-")]
        start = date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)
    except (ValueError, IndexError):
        return None
    t = date.today()
    return max(0, (t.year - start.year) * 12 + (t.month - start.month))


def profile(person_id: str) -> dict:
    """The grouped recruiting profile for one person, provenance attached to every field."""
    fields = current([person_id]).get(person_id, {})
    out = {"person_id": person_id}
    for group, names in GROUPS.items():
        g = {n: fields[n] for n in names if n in fields}
        if g:
            out[group] = g
    start = (fields.get("current_role_start_date") or {}).get("value")
    months = _months_since(start)
    if months is not None:
        out.setdefault("employment", {})["months_in_current_role"] = {"value": months, "level": "INFERENCE",
            "source_type": "computed", "source_url": None,
            "evidence_text": f"Computed from current_role_start_date {start}", "confidence": 0.9,
            "observed_at": _today(), "enriched_by": "server"}
    out["fields_present"] = sorted(fields)
    return out


# ---------------------------------------------------------------- extraction

def _clean_company(raw):
    if not raw:
        return None
    c = " ".join(str(raw).split()).strip()
    c = re.sub(r"^@+", "", c).strip()
    if not c or "://" in c or len(c) > 120:
        return None
    return c


def extract(person_id: str, user: dict, repos: list, location_country: str | None = None) -> list[dict]:
    """Deterministic entries from a GitHub profile dict. Facts only where the person declared them."""
    from . import location_norm
    entries = []
    today = _today()
    company = _clean_company(user.get("company"))
    if company:
        entries.append({"field": "current_company", "value": company, "level": "FACT",
                        "source_type": "github_profile", "evidence_text": f"GitHub profile company field: {company}",
                        "confidence": 0.9, "observed_at": today})
    if user.get("hireable") is True:
        entries.append({"field": "open_to_work_status", "value": "YES", "level": "FACT",
                        "source_type": "github_profile",
                        "evidence_text": "GitHub 'available for hire' flag is switched on on their public profile",
                        "confidence": 0.85, "observed_at": today})
    display, country = location_norm.normalize(user.get("location"))
    city = None
    if display and country and display != country and ", " in display:
        city = display.rsplit(", ", 1)[0]
    if not country and location_country:
        country = location_country
    if city:
        entries.append({"field": "current_city", "value": city, "level": "FACT", "source_type": "github_profile",
                        "evidence_text": f"GitHub profile location: {user.get('location')}", "confidence": 0.8,
                        "observed_at": today})
    if country:
        entries.append({"field": "current_country", "value": country, "level": "FACT",
                        "source_type": "github_profile" if user.get("location") else "location_table",
                        "evidence_text": f"Location resolves to {country}", "confidence": 0.8, "observed_at": today})
    years = []
    created = (user.get("created_at") or "")[:4]
    if created.isdigit():
        years.append(int(created))
    repo_years = [int((r.get("created_at") or "")[:4]) for r in repos if (r.get("created_at") or "")[:4].isdigit()]
    if repo_years:
        years.append(min(repo_years))
    if years:
        span = date.today().year - min(years)
        if span >= 1:
            entries.append({"field": "estimated_years_experience", "value": span, "level": "INFERENCE",
                            "source_type": "github_profile",
                            "evidence_text": f"Public GitHub activity since {min(years)} — a floor for experience, not the total",
                            "confidence": 0.4, "observed_at": today})
    return entries


def extract_for(person_id: str) -> list[dict]:
    """Extraction for one person, reading the tier-1 cache + location table."""
    if not TIER1_GITHUB.exists():
        return []
    db = sqlite3.connect(f"file:{TIER1_GITHUB}?mode=ro", uri=True)
    try:
        row = db.execute("SELECT api_status, user_json, repos_json FROM github_raw WHERE person_id = ?",
                         (person_id,)).fetchone()
    finally:
        db.close()
    if not row or row[0] != 200:
        return []
    try:
        user = json.loads(row[1] or "{}")
        repos = json.loads(row[2] or "[]")
    except (TypeError, ValueError):
        return []
    loc_country = None
    if ENRICHMENT.exists():
        db = sqlite3.connect(f"file:{ENRICHMENT}?mode=ro", uri=True)
        try:
            r = db.execute("SELECT country FROM talent_location WHERE person_id = ?", (person_id,)).fetchone()
            loc_country = r[0] if r else None
        except sqlite3.OperationalError:
            pass
        finally:
            db.close()
    return extract(person_id, user, repos, loc_country)


# ---------------------------------------------------------------- scoring

_RANKS = {"JUNIOR": 1, "MID": 2, "SENIOR": 3, "STAFF": 4, "LEAD": 4, "MANAGER": 4, "PRINCIPAL": 5, "EXECUTIVE": 6}


def _years_bucket(years: float) -> str:
    return "JUNIOR" if years < 2 else "MID" if years < 5 else "SENIOR" if years < 8 else "STAFF" if years < 12 else "PRINCIPAL"


def score_offer(person_id: str, offer: dict) -> dict:
    """Job-specific offer-acceptability score (0-100) with a visible breakdown. Computed, never stored.

    offer keys: salary_min, salary_max, currency, work_mode (REMOTE/HYBRID/ONSITE), country, city, seniority.
    Missing candidate data scores neutral and says so in the basis — unknowns are never hidden."""
    f = current([person_id]).get(person_id, {})
    val = lambda name: (f.get(name) or {}).get("value")
    parts, notes = {}, []

    otw = val("open_to_work_status")
    emp = val("employment_status")
    signals = val("career_signals") or []
    recent_signal = any(s.get("type") in ("recent_job_search_signal", "recent_layoff_signal",
                                           "recent_contract_end_signal", "freelance_availability_signal")
                          and (s.get("date") or "") >= _today()[:4] for s in signals)
    a = {"YES": 30, "LIKELY": 22, "UNKNOWN": 12, "NO": 3}.get(otw, 10)
    basis = f"open_to_work={otw or 'no data'}"
    if emp in ("BETWEEN_JOBS", "FREELANCE"):
        a = max(a, 24)
        basis += f", employment={emp}"
    if recent_signal:
        a = min(30, a + 3)
        basis += ", recent career signal"
    parts["availability"] = {"score": a, "max": 30, "basis": basis}

    est = val("estimated_current_salary") or {}
    exp = val("expected_salary") or {}
    omax, omin = offer.get("salary_max"), offer.get("salary_min")
    c = None
    if omax and est.get("max") and offer.get("currency") and est.get("currency") == offer["currency"]:
        ratio = omax / est["max"]
        c = 25 if ratio >= 1.1 else 20 if ratio >= 1.0 else 14 if ratio >= 0.9 else 8 if ratio >= 0.8 else 3
        basis = f"offered max {omax} vs estimated current max {est['max']} {est['currency']} (ratio {ratio:.2f})"
    elif omax and exp.get("min") and offer.get("currency") and exp.get("currency") == offer["currency"]:
        c = 22 if omax >= exp["min"] else 10
        basis = f"offered max {omax} vs expected min {exp['min']} {exp['currency']}"
    else:
        c = 12
        basis = "no comparable salary data (missing estimate, expected range, or currency mismatch) — neutral"
        notes.append("Compensation is a neutral score: no usable salary estimate for this person yet.")
    parts["compensation"] = {"score": c, "max": 25, "basis": basis}

    mode = (offer.get("work_mode") or "REMOTE").upper()
    ccountry, ccity = val("current_country"), val("current_city")
    relo = val("relocation_openness")
    if mode == "REMOTE":
        loc, basis = 20, "remote role — location does not block"
    elif offer.get("city") and ccity and offer["city"].lower() == str(ccity).lower():
        loc, basis = 20, f"same city ({ccity})"
    elif offer.get("country") and ccountry and offer["country"].lower() == str(ccountry).lower():
        loc, basis = (16 if relo == "YES" else 14), f"same country ({ccountry})"
    elif relo == "YES":
        loc, basis = 10, "different country, open to relocation"
    elif relo == "LIKELY":
        loc, basis = 7, "different country, likely open to relocation"
    elif relo == "NO":
        loc, basis = 0, "different country and not open to relocation"
    else:
        loc, basis = 4, "different country, relocation openness unknown"
    parts["location"] = {"score": loc, "max": 20, "basis": basis}

    want = (offer.get("seniority") or "").upper()
    have = val("seniority_level")
    if not have or have == "UNKNOWN":
        yrs = val("estimated_years_experience")
        have = _years_bucket(yrs) if yrs else None
    if want in _RANKS and have in _RANKS:
        diff = abs(_RANKS[want] - _RANKS[have])
        s = 15 if diff == 0 else 11 if diff == 1 else 7 if diff == 2 else 3
        basis = f"wanted {want}, candidate {have}"
    else:
        s, basis = 7, "seniority unknown on one side — neutral"
    parts["seniority"] = {"score": s, "max": 15, "basis": basis}

    m = 5
    mb = "no domain-interest data in the MVP — neutral"
    if otw == "YES":
        m = 8
        mb = "actively open to work"
    if recent_signal:
        m = min(10, m + 2)
        mb += ", recent job-search/career signal"
    parts["motivation"] = {"score": m, "max": 10, "basis": mb}

    total = sum(p["score"] for p in parts.values())
    return {"person_id": person_id, "offer_acceptability_score": total, "max": 100,
            "breakdown": parts, "notes": notes}
