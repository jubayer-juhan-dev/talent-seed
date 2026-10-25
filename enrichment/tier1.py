"""Tier-1 classifier: public GitHub profile + repos -> ontology-grounded talent evidence.

Ported from the ProspectMind bundle's tier1_harvester.py (Skills Graph v0.4 discipline):

    Talent -> Contribution -> Component -> Evidence -> Concept
    status: FACT | INFERENCE | UNKNOWN
    usage:  DECLARED | OBSERVED_USAGE | CONTRIBUTOR_USAGE | ADVANCED_USAGE

The maps and rules are unchanged from the bundle. Differences:
- input is a Talent Seed row (talent_seed column names) and output is keyed by person_id;
- forks are skipped: a fork's language/topics are someone else's work, not evidence;
- a GitHub account that no longer exists gives UNKNOWNs only.
"""

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SEED = Path(__file__).resolve().parents[1] / "ontology" / "ontology_seed.yaml"

# Topic / language -> ontology concept map.
# Explicit and reviewable on purpose: every row is a classification decision.
# (concept_id, usage_level, note)
TOPIC_MAP = {
    # --- skills ---
    "solidity": [("PM.SKILL.0002", "OBSERVED_USAGE", "topic on contract repos")],
    "smart-contract": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "smart-contracts": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "typescript": [("PM.SKILL.0001", "OBSERVED_USAGE", "topic")],
    "ts": [("PM.SKILL.0001", "OBSERVED_USAGE", "topic")],
    "rust": [("PM.SKILL.0003", "OBSERVED_USAGE", "topic")],
    "go": [("PM.SKILL.0004", "OBSERVED_USAGE", "topic")],
    "golang": [("PM.SKILL.0004", "OBSERVED_USAGE", "topic")],
    "python": [("PM.SKILL.0005", "OBSERVED_USAGE", "topic")],
    # --- tools ---
    "hardhat": [("PM.TOOL.0003", "OBSERVED_USAGE", "topic")],
    "foundry": [("PM.TOOL.0002", "OBSERVED_USAGE", "topic")],
    "forge": [("PM.TOOL.0002", "OBSERVED_USAGE", "topic")],
    "nextjs": [("PM.TOOL.0001", "OBSERVED_USAGE", "Next.js implies React")],
    "reactjs": [("PM.TOOL.0001", "OBSERVED_USAGE", "topic")],
    "react": [("PM.TOOL.0001", "OBSERVED_USAGE", "topic")],
    # --- supporting web3 tooling -> smart-contract development evidence ---
    "ethersjs": [("PM.SKILL.0009", "OBSERVED_USAGE", "contract-interaction lib")],
    "etherjs": [("PM.SKILL.0009", "OBSERVED_USAGE", "contract-interaction lib")],
    "web3modal": [("PM.SKILL.0009", "OBSERVED_USAGE", "dapp wallet tooling")],
    "metamask": [("PM.SKILL.0009", "OBSERVED_USAGE", "dapp wallet tooling")],
    "alchemy": [("PM.SKILL.0009", "OBSERVED_USAGE", "node infra tooling")],
    "chainlink": [("PM.SKILL.0009", "OBSERVED_USAGE", "oracle integration")],
    "erc721": [("PM.SKILL.0009", "OBSERVED_USAGE", "token-standard work")],
    "ipfs": [("PM.SKILL.0009", "OBSERVED_USAGE", "decentralized storage")],
    "remix": [("PM.SKILL.0009", "OBSERVED_USAGE", "contract IDE")],
    # --- conceptual skills (added 2026-10-20: these had ZERO evidence pool-wide
    # --- because no topic/language ever mapped to them) ---
    "api": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "rest-api": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "restful-api": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "api-development": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "api-design": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "openapi": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic")],
    "graphql": [("PM.SKILL.0006", "OBSERVED_USAGE", "topic: GraphQL APIs")],
    "ci-cd": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "cicd": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "continuous-integration": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "continuous-delivery": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "github-actions": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "gitops": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "devops": [("PM.SKILL.0012", "OBSERVED_USAGE", "topic")],
    "consensus": [("PM.SKILL.0011", "OBSERVED_USAGE", "topic")],
    "consensus-algorithm": [("PM.SKILL.0011", "OBSERVED_USAGE", "topic")],
    "raft": [("PM.SKILL.0011", "OBSERVED_USAGE", "topic")],
    "paxos": [("PM.SKILL.0011", "OBSERVED_USAGE", "topic")],
    "tendermint": [("PM.SKILL.0011", "OBSERVED_USAGE", "topic")],
    "distributed-systems": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "distributed-system": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "distributed-computing": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "distributed": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "microservices": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "p2p": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic: peer-to-peer systems")],
    "peer-to-peer": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    "libp2p": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic: libp2p networking stack")],
    "sql": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "database": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "databases": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "mysql": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "data-modeling": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "zero-knowledge": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zero-knowledge-proof": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zero-knowledge-proofs": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zk": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zkp": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zk-snark": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zk-snarks": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "zksnark": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic")],
    "circom": [("PM.SKILL.0010", "OBSERVED_USAGE", "topic: ZK circuit language")],
    "postgres": [("PM.TOOL.0006", "OBSERVED_USAGE", "topic")],
    "postgresql": [("PM.TOOL.0006", "OBSERVED_USAGE", "topic")],
    "docker": [("PM.TOOL.0004", "OBSERVED_USAGE", "topic")],
    "kubernetes": [("PM.TOOL.0005", "OBSERVED_USAGE", "topic")],
    "k8s": [("PM.TOOL.0005", "OBSERVED_USAGE", "topic: k8s")],
    "terraform": [("PM.TOOL.0007", "OBSERVED_USAGE", "topic")],
    "pytorch": [("PM.TOOL.0008", "OBSERVED_USAGE", "topic")],
    # --- responsive layout / CSS (PM.SKILL.0013) ---
    "css": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "css3": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "html-css": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "html-css-javascript": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "sass": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "scss": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "less": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "tailwindcss": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "tailwind": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "tailwind-css": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "bootstrap": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "styled-components": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic: CSS-in-JS")],
    "responsive": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "responsive-design": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "responsive-web-design": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "responsive-layout": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "mobile-first": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    # --- dapps are web applications ---
    "dapp": [("PM.SYS.0001", "OBSERVED_USAGE", "dapp topic -> web application")],
    "web3": [("PM.SYS.0001", "OBSERVED_USAGE", "web3 frontend work")],
    # --- ontology expansion batch 1: languages, frameworks, AI ---
    "javascript": [("PM.SKILL.0014", "OBSERVED_USAGE", "topic")],
    "js": [("PM.SKILL.0014", "OBSERVED_USAGE", "topic")],
    "es6": [("PM.SKILL.0014", "OBSERVED_USAGE", "topic")],
    "coffeescript": [("PM.SKILL.0014", "OBSERVED_USAGE", "topic")],
    "ejs": [("PM.SKILL.0014", "OBSERVED_USAGE", "topic")],
    "cpp": [("PM.SKILL.0015", "OBSERVED_USAGE", "topic")],
    "cplusplus": [("PM.SKILL.0015", "OBSERVED_USAGE", "topic")],
    "java": [("PM.SKILL.0016", "OBSERVED_USAGE", "topic")],
    "spring": [("PM.SKILL.0016", "OBSERVED_USAGE", "topic: Spring")],
    "spring-boot": [("PM.SKILL.0016", "OBSERVED_USAGE", "topic: Spring Boot")],
    "c": [("PM.SKILL.0017", "OBSERVED_USAGE", "topic")],
    "ai-agents": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "ai-agent": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "agents": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "multi-agent": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "mcp": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic: Model Context Protocol")],
    "mcp-server": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "model-context-protocol": [("PM.SKILL.0018", "OBSERVED_USAGE", "topic")],
    "llm": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "openai": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "claude": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "anthropic": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "chatgpt": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "gemini": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "prompt-engineering": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "langchain": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "ollama": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "local-llm": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "deepseek": [("PM.SKILL.0019", "OBSERVED_USAGE", "topic")],
    "vue": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "vuejs": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "vue3": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "nuxt": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "vuex": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "pinia": [("PM.TOOL.0009", "OBSERVED_USAGE", "topic")],
    "nodejs": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "node": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "express": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "expressjs": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "bun": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "nestjs": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "fastify": [("PM.TOOL.0010", "OBSERVED_USAGE", "topic")],
    "svelte": [("PM.TOOL.0011", "OBSERVED_USAGE", "topic")],
    "sveltekit": [("PM.TOOL.0011", "OBSERVED_USAGE", "topic")],
    "angular": [("PM.TOOL.0012", "OBSERVED_USAGE", "topic")],
    "angularjs": [("PM.TOOL.0012", "OBSERVED_USAGE", "topic")],
    "rxjs": [("PM.TOOL.0012", "OBSERVED_USAGE", "topic")],
    # --- batch 1 mapping-only rules (existing concepts) ---
    "docker-compose": [("PM.TOOL.0004", "OBSERVED_USAGE", "topic")],
    "hcl": [("PM.TOOL.0007", "OBSERVED_USAGE", "topic")],
    "html": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "html5": [("PM.SKILL.0013", "OBSERVED_USAGE", "topic")],
    "ethereum": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "blockchain": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "evm": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "bitcoin": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "solana": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "polygon": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "base": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "binance": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "starknet": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "stellar": [("PM.SYS.0003", "OBSERVED_USAGE", "topic")],
    "defi": [("PM.SYS.0004", "OBSERVED_USAGE", "topic")],
    "trading": [("PM.SYS.0004", "OBSERVED_USAGE", "topic")],
    "dex": [("PM.SYS.0004", "OBSERVED_USAGE", "topic")],
    "uniswap": [("PM.SYS.0004", "OBSERVED_USAGE", "topic")],
    "nft": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "erc20": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "truffle": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "web3js": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "ethereum-contract": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "ethereum-dapp": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "solidity-contracts": [("PM.SKILL.0009", "OBSERVED_USAGE", "topic")],
    "sqlite": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "prisma": [("PM.SKILL.0008", "OBSERVED_USAGE", "topic")],
    "security": [("PM.KNOW.0001", "OBSERVED_USAGE", "topic")],
    "privacy": [("PM.KNOW.0001", "OBSERVED_USAGE", "topic")],
    "static-analysis": [("PM.KNOW.0001", "OBSERVED_USAGE", "topic")],
    "encryption": [("PM.KNOW.0002", "OBSERVED_USAGE", "topic")],
    "cryptography": [("PM.KNOW.0002", "OBSERVED_USAGE", "topic")],
    "ed25519": [("PM.KNOW.0002", "OBSERVED_USAGE", "topic")],
    "pwa": [("PM.SYS.0001", "OBSERVED_USAGE", "topic: progressive web app")],
    "kafka": [("PM.SKILL.0007", "OBSERVED_USAGE", "topic")],
    # --- ontology expansion batch 2: languages, mobile, data, QA ---
    "bash": [("PM.SKILL.0020", "OBSERVED_USAGE", "topic")],
    "linux": [("PM.SKILL.0020", "OBSERVED_USAGE", "topic")],
    "zsh": [("PM.SKILL.0020", "OBSERVED_USAGE", "topic")],
    "machine-learning": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "deep-learning": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "tensorflow": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "scikit-learn": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "data-science": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "nlp": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "computer-vision": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "whisper": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "tts": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "speech-to-text": [("PM.SKILL.0021", "OBSERVED_USAGE", "topic")],
    "rails": [("PM.SKILL.0022", "OBSERVED_USAGE", "topic")],
    "ruby-on-rails": [("PM.SKILL.0022", "OBSERVED_USAGE", "topic")],
    "csharp": [("PM.SKILL.0023", "OBSERVED_USAGE", "topic")],
    "dotnet": [("PM.SKILL.0023", "OBSERVED_USAGE", "topic")],
    "laravel": [("PM.SKILL.0024", "OBSERVED_USAGE", "topic")],
    "wordpress": [("PM.SKILL.0024", "OBSERVED_USAGE", "topic")],
    "swift": [("PM.SKILL.0025", "OBSERVED_USAGE", "topic")],
    "swiftui": [("PM.SKILL.0025", "OBSERVED_USAGE", "topic"), ("PM.SKILL.0029", "OBSERVED_USAGE", "topic")],
    "flutter": [("PM.TOOL.0013", "OBSERVED_USAGE", "topic")],
    "android": [("PM.SKILL.0027", "OBSERVED_USAGE", "topic")],
    "jetpack-compose": [("PM.SKILL.0027", "OBSERVED_USAGE", "topic")],
    "testing": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "jest": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "pytest": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "e2e": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "playwright": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "cypress": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "vitest": [("PM.SKILL.0028", "OBSERVED_USAGE", "topic")],
    "ios": [("PM.SKILL.0029", "OBSERVED_USAGE", "topic")],
    "xcode": [("PM.SKILL.0029", "OBSERVED_USAGE", "topic")],
    "mongodb": [("PM.TOOL.0014", "OBSERVED_USAGE", "topic")],
    "mongoose": [("PM.TOOL.0014", "OBSERVED_USAGE", "topic")],
    "react-native": [("PM.TOOL.0015", "OBSERVED_USAGE", "topic")],
    "expo": [("PM.TOOL.0015", "OBSERVED_USAGE", "topic")],
    "fastapi": [("PM.TOOL.0016", "OBSERVED_USAGE", "topic")],
    "rag": [("PM.CAP.0006", "OBSERVED_USAGE", "topic")],
    "vector-database": [("PM.CAP.0006", "OBSERVED_USAGE", "topic")],
    "embeddings": [("PM.CAP.0006", "OBSERVED_USAGE", "topic")],
    "semantic-search": [("PM.CAP.0006", "OBSERVED_USAGE", "topic")],
    "knowledge-graph": [("PM.CAP.0006", "OBSERVED_USAGE", "topic")],
    "aws": [("PM.TOOL.0017", "OBSERVED_USAGE", "topic")],
    "aws-lambda": [("PM.TOOL.0017", "OBSERVED_USAGE", "topic")],
    "redis": [("PM.TOOL.0018", "OBSERVED_USAGE", "topic")],
    "flask": [("PM.TOOL.0019", "OBSERVED_USAGE", "topic")],
    "django": [("PM.TOOL.0020", "OBSERVED_USAGE", "topic")],
}

LANGUAGE_MAP = {  # repo primary language -> (concept, note)
    "Solidity": ("PM.SKILL.0002", "dominant repo language"),
    "TypeScript": ("PM.SKILL.0001", "repo language"),
    "Rust": ("PM.SKILL.0003", "repo language"),
    "Go": ("PM.SKILL.0004", "repo language"),
    "Python": ("PM.SKILL.0005", "repo language"),
    "SQL": ("PM.SKILL.0008", "repo language"),
    "CSS": ("PM.SKILL.0013", "repo language"),
    "SCSS": ("PM.SKILL.0013", "repo language"),
    "Sass": ("PM.SKILL.0013", "repo language"),
    "Less": ("PM.SKILL.0013", "repo language"),
    "JavaScript": ("PM.SKILL.0014", "repo language"),
    "C++": ("PM.SKILL.0015", "repo language"),
    "Java": ("PM.SKILL.0016", "repo language"),
    "C": ("PM.SKILL.0017", "repo language"),
    "Vue": ("PM.TOOL.0009", "repo language"),
    "Svelte": ("PM.TOOL.0011", "repo language"),
    "Dockerfile": ("PM.TOOL.0004", "repo language"),
    "HTML": ("PM.SKILL.0013", "repo language"),
    "HCL": ("PM.TOOL.0007", "repo language"),
    "CoffeeScript": ("PM.SKILL.0014", "repo language"),
    "EJS": ("PM.SKILL.0014", "repo language"),
    "Astro": ("PM.SYS.0001", "repo language"),
    "Shell": ("PM.SKILL.0020", "repo language"),
    "PowerShell": ("PM.SKILL.0020", "repo language"),
    "Jupyter Notebook": ("PM.SKILL.0021", "repo language"),
    "Ruby": ("PM.SKILL.0022", "repo language"),
    "C#": ("PM.SKILL.0023", "repo language"),
    "PHP": ("PM.SKILL.0024", "repo language"),
    "Swift": ("PM.SKILL.0025", "repo language"),
    "Kotlin": ("PM.SKILL.0026", "repo language"),
    "Dart": ("PM.TOOL.0013", "repo language"),
    "Objective-C": ("PM.SKILL.0029", "repo language"),
}

UNKNOWNS = ["Role seniority (beyond proxy)", "Availability / open-to-work",
            "Rate expectations", "Smart-contract audit authorship"]


def load_concepts():
    """{concept_id: {id, type, name}} from the seed YAML (line parser, no yaml dependency)."""
    concepts = {}
    cur = None
    for line in SEED.read_text().splitlines():
        s = line.strip()
        if s.startswith("- id: PM."):
            cur = {"id": s.split(":", 1)[1].strip()}
            concepts[cur["id"]] = cur
        elif cur is not None and s.startswith("type:"):
            cur["type"] = s.split(":", 1)[1].strip()
        elif cur is not None and s.startswith("name:"):
            cur["name"] = s.split(":", 1)[1].strip().strip('"')
    return concepts


def ev(concept_id, concepts, status, usage, confidence, source, note, contribution=""):
    c = concepts.get(concept_id, {})
    return {"concept_id": concept_id, "concept": c.get("name", concept_id), "type": c.get("type", "?"),
            "status": status, "usage": usage, "confidence": confidence, "source": source,
            "contribution": contribution, "note": note}


def unknown(concept, note):
    return {"concept_id": None, "concept": concept, "type": "?", "status": "UNKNOWN", "usage": "UNKNOWN",
            "confidence": 0.0, "source": "none", "contribution": "", "note": note}


def before(row):
    return {"commits": row["commit_count"], "repos": row["repository_count"],
            "active_days": row["active_days_in_window"], "ecosystems": row["ecosystem_count"],
            "top_ecosystems": list(row["top_level_ecosystems"] or [])[:5], "country": row["country"]}


def classify(row, user, repos, concepts, now=None):
    """row: Talent Seed row (dict); user/repos: GitHub API bodies, user=None when the account is gone."""
    now = now or datetime.now(timezone.utc)
    talent = {"person_id": row["person_id"], "name": row["display_name"],
              "github": (user or {}).get("login") or row["github_login"], "cohort": row["priority_cohort"]}
    if user is None:
        return {"talent": talent, "talent_seed_before": before(row), "github_profile": None,
                "top_languages": {}, "top_topics": {}, "forks_skipped": 0,
                "evidence": [unknown(u, "GitHub account not found (deleted or renamed away)") for u in UNKNOWNS],
                "ontology_candidates": {"unmapped_topics": {}, "unmapped_languages": {}}}

    evidence = []
    unmapped_topics = Counter()
    unmapped_langs = Counter()
    own = [r for r in repos if not r.get("fork")]

    topic_hits = Counter()
    lang_hits = Counter()
    for r in own:
        if r.get("language"):
            lang_hits[r["language"]] += 1
        for t in r.get("topics") or []:
            topic_hits[t.lower()] += 1

    seen = set()

    def plural(n, word="repo"):
        return f"{n} {word}" if n == 1 else f"{n} {word}s"

    def add_fact(cid, usage, conf, source, note, contribution=""):
        key = (cid, usage)
        if key in seen:
            return
        seen.add(key)
        evidence.append(ev(cid, concepts, "FACT", usage, conf, source, note, contribution))

    # --- FACTs from topics ---
    for topic, n in topic_hits.items():
        if topic in TOPIC_MAP:
            for cid, usage, note in TOPIC_MAP[topic]:
                add_fact(cid, usage, 0.9, f"github:topics ({plural(n)})",
                         f"topic '{topic}' on {plural(n)} — {note}",
                         contribution=f"{plural(n)} tagged '{topic}'")
        else:
            unmapped_topics[topic] = n

    # --- FACTs from languages ---
    total = sum(lang_hits.values()) or 1
    for lang, n in lang_hits.items():
        if lang in LANGUAGE_MAP:
            cid, note = LANGUAGE_MAP[lang]
            usage = "CONTRIBUTOR_USAGE" if n >= 10 else "OBSERVED_USAGE"
            add_fact(cid, usage, 0.85, f"github:languages ({plural(n)} of {total} repos)",
                     f"{lang} primary language in {plural(n)} — {note}")
        else:
            unmapped_langs[lang] = n

    # --- FACTs from profile ---
    if user.get("blog"):
        evidence.append(ev("PM.SYS.0001", concepts, "FACT", "DECLARED", 0.7,
                           "github:profile.blog", f"personal site: {user['blog']}",
                           contribution="maintains a public portfolio site"))
    if user.get("twitter_username"):
        evidence.append({"concept_id": None, "concept": "Outreach channel (X)", "type": "IDENTITY",
                         "status": "FACT", "usage": "DECLARED", "confidence": 1.0,
                         "source": "github:profile.twitter_username", "contribution": "public X handle",
                         "note": f"@{user['twitter_username']} — feeds Identity Resolution"})
    # LinkedIn: from GitHub social accounts, else a website field pointing at linkedin.com
    linkedin = next((a["url"] for a in user.get("social_accounts") or [] if a.get("provider") == "linkedin"), None)
    li_source = "github:profile.social_accounts"
    if not linkedin and "linkedin.com/" in (user.get("blog") or "").lower():
        linkedin, li_source = user["blog"], "github:profile.blog"
    if linkedin:
        evidence.append({"concept_id": None, "concept": "Outreach channel (LinkedIn)", "type": "IDENTITY",
                         "status": "FACT", "usage": "DECLARED", "confidence": 1.0,
                         "source": li_source, "contribution": "public LinkedIn link",
                         "note": f"{linkedin} — feeds Identity Resolution"})
    if user.get("location"):
        evidence.append({"concept_id": None, "concept": "Location cross-check", "type": "IDENTITY",
                         "status": "FACT", "usage": "DECLARED", "confidence": 0.9,
                         "source": "github:profile.location", "contribution": "self-reported location",
                         "note": f"'{user['location']}' vs Talent Seed country '{row['country'] or '?'}'"})

    # --- INFERENCEs ---
    solidity_repos = lang_hits.get("Solidity", 0)
    has_tooling = any(t in topic_hits for t in ("hardhat", "foundry", "forge"))
    if solidity_repos >= 5 and has_tooling:
        evidence.append(ev("PM.ROLE.0005", concepts, "INFERENCE", "CONTRIBUTOR_USAGE",
                           0.9, "derived:languages+topics",
                           f"{solidity_repos} Solidity repos + contract tooling "
                           f"({', '.join(t for t in ('hardhat', 'foundry', 'forge') if t in topic_hits)})",
                           contribution="sustained contract-code output with professional tooling"))
    frontend_sig = sum(topic_hits.get(t, 0) for t in ("nextjs", "reactjs", "react"))
    if frontend_sig >= 5 and (solidity_repos >= 3 or lang_hits.get("TypeScript", 0) >= 3):
        evidence.append(ev("PM.ROLE.0003", concepts, "INFERENCE", "CONTRIBUTOR_USAGE",
                           0.7, "derived:topics+languages",
                           f"frontend ({frontend_sig} react/nextjs topics) + backend/contract code",
                           contribution="ships across UI and contract layers"))
    elif frontend_sig >= 5:
        evidence.append(ev("PM.ROLE.0001", concepts, "INFERENCE", "OBSERVED_USAGE",
                           0.6, "derived:topics",
                           f"{frontend_sig} react/nextjs topic hits",
                           contribution="repeated frontend-framework usage"))
    if "openzeppelin" in topic_hits:
        evidence.append(ev("PM.KNOW.0001", concepts, "INFERENCE", "OBSERVED_USAGE",
                           0.55, "derived:topics",
                           "builds on audited security libraries (using, not authoring — "
                           "audit capability itself stays UNKNOWN)",
                           contribution=f"{topic_hits['openzeppelin']} repos use OpenZeppelin"))
    # seniority proxy — explicitly labeled as proxy
    try:
        age_y = (now - datetime.fromisoformat(user.get("created_at", ""))).days / 365.25
    except ValueError:
        age_y = 0
    commits = int(row["commit_count"] or 0)
    if age_y >= 4 and (user.get("followers") or 0) >= 10 and commits >= 200:
        evidence.append({"concept_id": None, "concept": "Seniority band: senior", "type": "INFERENCE",
                         "status": "INFERENCE", "usage": "OBSERVED_USAGE", "confidence": 0.6,
                         "source": "derived:profile+talent-seed",
                         "contribution": f"{age_y:.1f}y account, {user.get('followers')} followers, {commits} commits",
                         "note": "proxy only — real seniority needs PR/ownership evidence"})

    # --- explicit UNKNOWNs (honest, not guessed) ---
    for u in UNKNOWNS:
        evidence.append(unknown(u, "no public signal — talent-supplied or Benoît-side data needed"))

    return {
        "talent": talent,
        "talent_seed_before": before(row),
        "github_profile": {
            "followers": user.get("followers"), "account_since": (user.get("created_at") or "")[:10],
            "location": user.get("location"), "blog": user.get("blog"),
            "twitter": user.get("twitter_username"), "public_repos": user.get("public_repos"),
            "repos_analyzed": len(own),
        },
        "forks_skipped": len(repos) - len(own),
        "top_languages": dict(lang_hits.most_common(8)),
        "top_topics": dict(topic_hits.most_common(15)),
        "evidence": evidence,
        "ontology_candidates": {
            "unmapped_topics": dict(unmapped_topics.most_common(10)),
            "unmapped_languages": dict(unmapped_langs.most_common(5)),
        },
    }


def demo_md(results, sample):
    """Cohort summary + before/after tables for `sample` (list of results)."""
    n = len(results)
    status = Counter(e["status"] for r in results for e in r["evidence"])
    with_fact = sum(any(e["status"] == "FACT" and e["concept_id"] for e in r["evidence"]) for r in results)
    gone = sum(r["github_profile"] is None for r in results)
    concepts = Counter(e["concept"] for r in results for e in r["evidence"] if e["status"] != "UNKNOWN" and e["concept_id"])
    growth = Counter()
    for r in results:
        growth.update(r["ontology_candidates"]["unmapped_topics"].keys())
    L = ["# Tier-1 enrichment — P1 cohort before → after", "",
         f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · public GitHub data only · forks skipped_", "",
         "## Cohort summary", "",
         f"- People: **{n}** · with at least one concept FACT: **{with_fact}** ({with_fact / max(n, 1):.0%})"
         f" · GitHub account not found: **{gone}**",
         f"- Evidence rows: FACT {status['FACT']} · INFERENCE {status['INFERENCE']} · UNKNOWN {status['UNKNOWN']}", "",
         "| Concept (FACT or INFERENCE) | People |", "|---|---|"]
    L += [f"| {c} | {k} |" for c, k in concepts.most_common(20)]
    L += ["", "**Top ontology growth candidates** (unmapped topics, people with each — for human review, "
          "not auto-added): " + ", ".join(f"{t} ({k})" for t, k in growth.most_common(25)), ""]
    for r in sample:
        t, b = r["talent"], r["talent_seed_before"]
        L += [f"## {t['name']} ([@{t['github']}](https://github.com/{t['github']})) — {t['cohort']} · `{t['person_id']}`",
              "",
              f"**BEFORE (Talent Seed row):** {b['commits']} commits · {b['repos']} repos · "
              f"{b['active_days']} active days · {b['ecosystems']} ecosystems ({', '.join(b['top_ecosystems'])})",
              "", "**AFTER (classified talent evidence):**", "",
              "| Concept | Type | Status | Usage | Conf | Evidence |", "|---|---|---|---|---|---|"]
        for e in r["evidence"]:
            L.append(f"| {e['concept']} | {e['type']} | **{e['status']}** | {e['usage']} | "
                     f"{e['confidence']:.2f} | {e['note']} |")
        L += ["", f"_Top languages: {', '.join(f'{k}×{v}' for k, v in r['top_languages'].items()) or 'none'}_", ""]
    return "\n".join(L)
