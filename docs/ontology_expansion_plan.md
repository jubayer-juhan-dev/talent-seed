# Ontology expansion plan (agreed 2026-10-25)

Grow the Talent Ontology from **42 to 109 concepts** (67 new) plus 26 mapping-only rules, all fed
from signals we already hold. Counts are distinct people among the 13,408 harvested (own repos,
forks skipped) in `data/tier1_github.sqlite`; "lang" = primary repo language, "topic" = repo topic.

Rules for this plan:
- Languages, frameworks and databases are one concept each (split, not grouped).
- A concept needs an evidence source; candidates under ~65 people wait for code-scan (c1) evidence.
- New concepts are loaded from the cache — no GitHub re-scan. Roles (AI Engineer, Mobile Engineer)
  get evidence from AI enrichment (e5), not from topics.

## Steps
1. `scripts/e6_reclassify_cache.py --concepts <ids>` — reusable version of the one-off loader used
   for PM.SKILL.0013 (re-classify from cache, load only the given concepts, e2 evidence ids).
2. Per batch: concepts into `ontology/ontology_seed.yaml` → `load_ontology.py` check → insert only
   the new concept + family rows into Neon → topic/language rules in `enrichment/tier1.py`.
3. Per batch: run e6 for the batch's concepts; check counts against the tables below.
4. Per batch: verify in the app (picker counts, dry-run extraction), update affected jobs.
5. Per batch: commit + push.
Later: e5 for the two new roles, c1 library registry additions, persist j2 growth candidates,
harvest P3 (coverage), refresh loop (runbook Step 6).

## Batch 1 — 11 concepts (+9 mappings)
| Concept | Type | People | Signals |
|---|---|---|---|
| JavaScript | SKILL | 6,711 | lang JavaScript; topics javascript, js, es6 |
| C++ | SKILL | 2,081 | lang C++; topics cpp, cplusplus |
| Java | SKILL | 2,194 | lang Java; topics java, spring, spring-boot |
| C | SKILL | 1,746 | lang C; topic c |
| AI Agents & Tool Use (MCP) | SKILL | 787 | ai-agents, ai-agent, agents, multi-agent, mcp, mcp-server, model-context-protocol |
| Vue | TOOL | 666 | lang Vue; vue, vuejs, vue3, nuxt, vuex, pinia |
| LLM Application Development | SKILL | 588 | llm, openai, claude, anthropic, chatgpt, gemini, prompt-engineering, langchain, ollama |
| Node.js | TOOL | 527 | nodejs, node, express, expressjs, bun, nestjs, fastify |
| Svelte | TOOL | 263 | lang Svelte; svelte, sveltekit |
| Angular | TOOL | 70 | angular, angularjs, rxjs |
| AI Engineer | ROLE | (e5) | inferred from the AI concepts |

## Batch 2 — 20 concepts
| Concept | Type | People | Signals |
|---|---|---|---|
| Shell Scripting / Linux | SKILL | 2,992 | lang Shell; bash, linux, zsh |
| Machine Learning | SKILL | 1,170 | lang Jupyter Notebook; machine-learning, deep-learning, tensorflow, scikit-learn, data-science |
| Ruby | SKILL | 929 | lang Ruby; rails, ruby-on-rails |
| C# | SKILL | 913 | lang C#; csharp, dotnet |
| PHP | SKILL | 909 | lang PHP; laravel, wordpress |
| Swift | SKILL | 786 | lang Swift; swift, swiftui |
| Kotlin | SKILL | 600 | lang Kotlin |
| Flutter (Dart) | TOOL | 432 | lang Dart; flutter |
| Android Development | SKILL | 202 | android, jetpack-compose |
| Automated Testing | SKILL | 186 | testing, jest, pytest, e2e, playwright, cypress, vitest |
| iOS Development | SKILL | 169 | ios, swiftui, xcode |
| MongoDB | TOOL | 114 | mongodb, mongoose |
| React Native | TOOL | 110 | react-native, expo |
| FastAPI | TOOL | 104 | fastapi |
| RAG / Retrieval | CAPABILITY | 97 | rag, vector-database, embeddings |
| AWS | TOOL | 84 | aws, aws-lambda |
| Redis | TOOL | 84 | redis |
| Flask | TOOL | 83 | flask |
| Django | TOOL | 61 | django |
| Mobile Engineer | ROLE | (e5) | inferred from the mobile concepts |

## Batch 3 — 13 concepts
| Concept | Type | People | Signals |
|---|---|---|---|
| Bitcoin & Lightning | SYSTEM | 440 | bitcoin, lightning-network, lightning, ordinals |
| Haskell | SKILL | 391 | lang Haskell |
| Game / 3D Development | SKILL | 276 | game, gamedev, threejs, godot, webgl |
| Bots (Telegram / Discord) | SYSTEM | 246 | telegram-bot, discord-bot, telegram, discord, bot |
| Scala | SKILL | 216 | lang Scala |
| Solana | SYSTEM | 198 | solana, anchor |
| Desktop App Development | SKILL | 165 | electron, tauri, desktop-app |
| Elixir | SKILL | 164 | lang Elixir |
| Monitoring & Observability | SKILL | 148 | monitoring, observability, prometheus, grafana, opentelemetry |
| Wallets | SYSTEM | 144 | wallet, crypto-wallet |
| Chrome Extensions | SYSTEM | 120 | chrome-extension, browser-extension |
| WebAssembly | SKILL | 111 | wasm, webassembly |
| Nostr | SYSTEM | 106 | nostr |

## Batch 4 — crypto-specific, 7 concepts
| Concept | Type | People | Signals |
|---|---|---|---|
| Formal Verification | KNOWLEDGE | 182 | lang Lean/Coq; formal-verification, certora |
| Payments & Stablecoins | SYSTEM | 161 | payments, usdc, stablecoin, x402, stripe |
| Move (Sui / Aptos) | SKILL | 152 | lang Move; sui, aptos |
| Cairo (Starknet) | SKILL | 139 | lang Cairo; starknet |
| Oracles | SYSTEM | 73 | oracle, chainlink, pyth |
| MEV & Trading Infrastructure | KNOWLEDGE | 70 | mev, flashbots, arbitrage, trading-bot |
| Cross-chain / Bridges | SYSTEM | 65 | bridge, cross-chain, ibc, layerzero |

## Batch 5 — general engineering, 16 concepts
| Concept | Type | People |
|---|---|---|
| Lua | SKILL | 527 |
| AI-Assisted Development | SKILL | 509 |
| Nix | TOOL | 311 |
| Assembly / Reverse Engineering | SKILL | 267 |
| Embedded & IoT | SKILL | 255 |
| Real-time Communication | SKILL | 227 |
| Front-end Build Tooling | TOOL | 222 |
| Compilers & Language Tooling | SKILL | 181 |
| Data Visualization | SKILL | 165 |
| Zig | SKILL | 147 |
| Algorithms & Data Structures | KNOWLEDGE | 140 |
| Authentication & Identity | SKILL | 130 |
| R | SKILL | 129 |
| Backend-as-a-Service | TOOL | 115 |
| GPU / CUDA Programming | SKILL | 113 |
| Front-end State Management | SKILL | 103 |

## Mapping-only rules (no new concept)
With batch 1: Dockerfile lang, docker-compose → Docker · HCL → Terraform · HTML lang, html, html5 →
Responsive UI & CSS · ethereum, blockchain, evm, bitcoin, solana → L1/L2 blockchain network ·
defi, trading → DeFi protocol · nft, erc20, erc721 → Smart Contract Development · sqlite → SQL &
Data Modeling · security, privacy → Application Security · encryption → Cryptography.

With the batch that adds the target: Objective-C → iOS Development · PowerShell → Shell Scripting ·
CoffeeScript, EJS → JavaScript · GDScript → Game / 3D · QML → Desktop App Development · Astro lang,
pwa → Web application · cryptography, ed25519 → Cryptography · prisma → SQL & Data Modeling ·
truffle, web3js, ethereum-contract, ethereum-dapp, solidity-contracts → Smart Contract Development ·
dex, uniswap → DeFi protocol · polygon, base, binance, starknet, stellar → L1/L2 blockchain network ·
nlp, computer-vision, whisper, tts, speech-to-text → Machine Learning · local-llm, deepseek → LLM
Application Development · semantic-search, knowledge-graph → RAG · static-analysis → Application
Security · kafka → Distributed Systems.

## Deferred (wait for code-scan evidence)
Account Abstraction (39), Indexing / The Graph (43), Stellar/Soroban (46), DAO & Governance (56).
