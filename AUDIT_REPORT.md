# CSC Mitra AI — Phase 1 Audit Report

**Scope:** `csc-mitra-ai-voice-start.zip` (extracted repo: `csc-mitra-ai/`)
**Method:** Full file inventory, read-through of every backend module, dependency grep across the whole tree, byte-compile of all `.py` files, and an actual run of the existing test suite. No code was changed to produce this report.

---

## 0. Bottom line, before the details

The brief this repo came with asks for a 17-subsystem "AI Governance Operating System" (LangGraph orchestration, 15 async agents, streaming realtime voice, hybrid RAG, multi-tier HITL, OpenTelemetry/Prometheus/Grafana, RBAC/OAuth2, etc.), to be delivered as one finished, tested, zipped package.

**That system does not exist in this repo, and this repo has already been through exactly this request once before.** `CLEANUP_NOTES.md` (already in the zip) documents a prior session where an uploaded "16-agent LangGraph governance OS" merge request was investigated and found to describe unwired scaffolding — `backend/agents/`, `backend/graph/`, `backend/services/`, `backend/workflows/`, `backend/models/`, `backend/db/` all existed as files but were imported by nothing that actually ran, plus a broken FastAPI `main.py` that imported a package that didn't exist. That prior session deleted the dead scaffolding, kept the real working Streamlit app, and wrote: *"Building it is a substantial, multi-week+ engineering effort, not a cleanup."*

My independent audit reaches the same conclusion. I'm not going to attempt the full 17-item build in one pass — doing so blindly would almost certainly recreate the exact problem that was already cleaned up once (impressive-looking files that nothing calls). Below is the real inventory, what's actually solid and worth keeping, what's actually broken, and a phased plan. **Section 6 is where I need your input** on what to build first.

---

## 1. What's actually in the repo

```
csc-mitra-ai/
├── app.py                     Modern Streamlit entry point
├── streamlit_app.py           Legacy entry point (try/except-wrapped imports)
├── pages/                     6 Streamlit multipage-app pages
│   ├── 1_CSC_Assistant.py     Chat UI → backend.mas_engine.ask()
│   ├── 2_Grievance_Redressal.py
│   ├── 3_Knowledge_Base.py    Document/URL ingestion UI (admin)
│   ├── 4_VLE_Dashboard.py
│   ├── 5_Officer_Dashboard.py
│   └── 6_Admin_Dashboard.py
├── backend/
│   ├── mas_engine.py (1199 lines)   The orchestrator — see §3
│   ├── database.py (302 lines)      pgvector store + cosine search (psycopg2)
│   ├── knowledge.py (483 lines)     Ingestion: chunking, parent/child, metadata
│   ├── document_extractors.py       PDF/DOCX/TXT/CSV/XLSX/PPTX → text
│   ├── crawler.py                   BFS crawler for allow-listed gov domains
│   ├── guardrails.py                Domain allowlist (70+ official CSC/gov domains)
│   ├── hitl.py                      SQLite human-review queue
│   ├── voice_assistant.py           OpenAI Whisper STT + OpenAI TTS (turn-based)
│   ├── adaptive_response.py         Response-mode detection, profile context
│   ├── builtin_guides.py (1008 l.)  Hand-written offline fallback content
│   ├── core_knowledge_pack.py (711) Structured service-record builder
│   ├── service_catalog.py           Official-URL lookup by keyword
│   ├── tavily_search.py             Web-search fallback (consent-gated)
│   ├── voice/                       ⚠️ EMPTY — see §4.1
│   ├── llm/                         Config-driven LLM router — see §3, genuinely good
│   └── tests/test_llm_manager.py    6 tests, all passing (verified below)
├── docs/, ENTRY_POINTS.md, VERIFICATION.md, backend/ARCHITECTURE.md
│                                    ⚠️ STALE — describe the removed scaffolding, see §4.2
├── data/*/README.md                 Placeholder folders, no actual seed data
└── assets/css/styles.css            ⚠️ DEAD — never loaded by any page, see §4.1
```

**Verified, not assumed:**
- `python3 -m py_compile` on every `.py` file in the repo → **0 syntax errors**.
- `cd backend && python -m pytest tests/test_llm_manager.py -v` → **6/6 passed**, no network calls (provider calls are monkeypatched).
- Confirmed by grep: nothing in the codebase imports `backend.voice`, `backend.agents`, `backend.graph`, `backend.services`, `backend.workflows`, `backend.models`, or `backend.db`. `backend/__init__.py` was already patched (in the prior session) to stop eagerly importing a since-deleted `agents` package.

---

## 2. What's genuinely solid — preserve this, don't rebuild it

The brief says "preserve working functionality" and it's worth being specific about what's actually good, because a from-scratch rewrite would throw it away:

- **`backend/llm/`** — a real config-driven model router: YAML model catalog (`config/models.yaml`), per-model circuit breaker (`health.py`), rolling success-rate/latency telemetry from real call outcomes (`telemetry.py`), a scorer that blends priority + reliability + speed + cost (`scoring.py`, free models preferred), and automatic fallback that doesn't penalize a model's health for a validator (guardrail) rejection vs. an actual failure. This already covers a meaningful chunk of the brief's item #16 (LLM Manager: dynamic routing, health monitoring, automatic fallback, cost optimization). It has real tests and I ran them — 6/6 pass.
- **`mas_engine.ask()`** — despite the misleading name (see §4.3), this is a coherent, sensible single-agent pipeline: try local built-in context → pgvector search → (if still empty and user consented) Tavily web search restricted to allow-listed domains → confidence scoring → HITL routing if confidence is low or child/minor PII is detected → PII redaction before anything goes to a cloud LLM → LLM call via the manager above → output guardrail check for leaked internal terms → DPDP consent notice appended. That's a real, working retrieval-guardrail-HITL loop, not a toy.
- **Guardrails allowlist** (`guardrails.py`) — 70+ real official CSC/government domains, actually enforced on every retrieved source and every suggested URL.
- **DPDP-aware PII handling** — Aadhaar/PAN/email/phone/IFSC/account-number/DOB regexes, redaction before cloud calls, extra gating when child/minor data is detected alongside personal data.
- **Multi-format ingestion pipeline** (`knowledge.py` + `document_extractors.py`) — PDF/DOCX/TXT/CSV/XLSX/PPTX extraction, parent/child recursive chunking with overlap, per-chunk metadata, document IDs. This is a real foundation for the "hybrid RAG" upgrade in §5 — the ingestion side doesn't need to be rebuilt, only the retrieval side (see below).
- **README.md and CLEANUP_NOTES.md** — accurate, honest, and worth trusting over every other doc in the repo (see §4.2).

---

## 3. Naming vs. reality: `mas_engine.py`

The file is called "mas_engine" (multi-agent system engine) and `backend/ARCHITECTURE.md` describes a "Multi-Agent System (backend/agents/)" with 8 separate agents (intent, service discovery, eligibility, document verification, compliance, workflow guidance, grievance, fusion). **None of that exists.** `mas_engine.py` is a single 1199-line procedural module with 39 flat functions and one public entry point, `ask()`. It does language detection, PII redaction, sentiment prefixing, DPDP notice generation, confidence scoring, HITL routing, response formatting, and the LLM call, all in one file. It works, but it's a god-module, and its name actively documents something false. This is the clearest instance of a broader pattern (see next section).

---

## 4. Audit findings

### 4.1 Dead code
| Item | Finding |
|---|---|
| `backend/voice/`, `backend/voice/stt/`, `backend/voice/tts/` | Three empty `__init__.py` files, nothing else. Zero references anywhere in the codebase (grepped). Leftover scaffolding from the same aspirational architecture the prior session already removed elsewhere — this one was missed. |
| `assets/css/styles.css` | Exists, has real CSS, is **never loaded** by any page (grepped every `.py` file — zero references). `VERIFICATION.md` claims it's wired up; it isn't. Because of this, individual pages hand-roll their own inline `<style>` blocks instead of sharing one stylesheet — inconsistent styling as a direct consequence. |

### 4.2 Documentation drift (the highest-leverage finding)
Five documents in this repo describe an architecture that was deleted:

- `ENTRY_POINTS.md` — lists `backend/agents/`, `backend/services/`, `backend/workflows/`, `backend/models/`, `backend/graph/`, `backend/db/` as existing packages with working imports, and gives verification commands (`from backend.agents import fusion_agent`) that would fail today.
- `VERIFICATION.md` — a "✅ Fixed" checklist that checks off the existence of the same removed packages, and checks off `assets/css/styles.css` as wired up (§4.1 shows it isn't).
- `docs/architecture.md`, `docs/workflow.md` — describe the 8-agent pipeline (intent → service discovery → eligibility → document verification → workflow guidance) as the live system design, with worked examples.
- `backend/ARCHITECTURE.md` — a module docstring describing RAG services, a multi-agent system, workflow engines, and LangGraph integration, none of which back the actual `backend/` package.

Only `README.md` and `CLEANUP_NOTES.md` reflect reality. **This matters beyond tidiness**: `backend/CODEX_PROMPT.md` (already in the repo) and the brief that came with this upload both describe roughly the same fictional 8-16-agent LangGraph system — it's a reasonable guess that these stale docs are exactly what's been feeding into repeated "upgrade this to the full architecture" requests, including the one that produced this session. Fixing the docs is cheap and stops the cycle.

### 4.3 Duplicate code
- `_secret(name, default="")` — the "check `st.secrets`, fall back to `os.getenv`" helper — is copy-pasted **identically** across `database.py`, `guardrails.py`, `hitl.py`, and `mas_engine.py`, plus a near-identical public variant `secret()` in `voice_assistant.py`. Five copies of the same ~10-line function.
- PII regex patterns (Aadhaar/PAN/email/phone/IFSC/account-number) are defined independently in both `mas_engine.py` (7 labeled patterns) and `hitl.py` (6 unlabeled patterns, a near-subset). If one gets updated (e.g., a new PII pattern added) the other silently doesn't.
- `mas_engine.py` naming: see §3.

### 4.4 Configuration inconsistency
Two different "environment template" files exist and **disagree with each other and with the code**:
- `.env.example` (repo root) — references `DATABASE_URL`, `POSTGRES_USER`/`POSTGRES_HOST`/`POSTGRES_PORT`, ChromaDB paths, `JWT_SECRET`, SMTP notification settings, Sentry DSN, OCR/document-verification feature flags. **None of these env vars are read anywhere in the actual code.**
- `backend/secrets.toml.txt` — references `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `HITL_CONFIDENCE_THRESHOLD`, `DPDP_ALLOW_CHILD_DATA_CLOUD`, `CSC_ALLOWED_DOMAINS`, etc. — this one **matches what `database.py`, `hitl.py`, and `mas_engine.py` actually read** (verified: `database.py`'s `DB_SECRET_NAMES = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")`).

A new deployer who follows the root `.env.example` (the more prominent, conventionally-named file) will set `POSTGRES_HOST` and wonder why the database connection fails, because the code is looking for `DB_HOST`. This is a real, reproducible bug in the onboarding path, not a style nit.

### 4.5 Architectural coupling
- **sys.path hacking, inconsistently.** `app.py` puts the repo root on `sys.path`. `streamlit_app.py` puts both the repo root *and* its parent on `sys.path`. Each page under `pages/` independently reconstructs `parent_dir`/`backend_dir` and inserts both. `backend/mas_engine.py` itself imports its siblings flat (`from database import vector_search`, not `from backend.database import ...`), which only works because `backend/` is *also* on `sys.path` — meaning the package is simultaneously importable as `backend.X` (from pages) and as bare `X` (from within itself), and several pages try/except both forms defensively (`pages/1_CSC_Assistant.py` tries `from backend.mas_engine import ask`, falls back to `from mas_engine import ask`). This works today but is fragile: it depends on execution order of `sys.path.insert` across files that don't coordinate, and it will bite the first time this stops being a single-process Streamlit app.
- **No connection pooling.** `database.py` opens a fresh `psycopg2.connect()` on every `vector_search()`/`store_vector()` call and closes it at the end. Fine at low concurrency, a real bottleneck under load.
- **Fully synchronous / blocking.** Every DB call, every LLM call, every embedding call is a blocking function call — consistent with Streamlit's execution model (each user interaction reruns the script top-to-bottom), but worth naming explicitly because the brief asks for "async everywhere" and "streaming everywhere," which is **not a drop-in change** — see §5's note on voice.

---

## 5. Gap analysis against the 17-item brief

| # | Brief item | Current state | Real gap |
|---|---|---|---|
| 1 | LangGraph orchestration | Not present; prior attempt was dead scaffolding | Full build. Also: LangGraph's graph-of-nodes model is a natural fit for a request pipeline that already exists conceptually in `mas_engine.ask()` — this is the highest-value structural rewrite if you want true multi-agent behavior later, but see §6 on sequencing. |
| 2 | Executive orchestrator | N/A | Only makes sense once #1 exists |
| 3 | Capability registry | N/A | Only makes sense once #1 exists |
| 4 | 15 named agents | `mas_engine.py` does all of this as functions, not agents | Real decomposition work, not just file-splitting — needs actual interface boundaries |
| 5 | Realtime streaming voice (VAD, barge-in, no send button) | Turn-based Whisper STT + OpenAI TTS, request/response only | **This is not a Streamlit-native feature.** Streamlit reruns the whole script per interaction; it has no persistent bidirectional connection. True barge-in/VAD/continuous-conversation needs a WebSocket/WebRTC audio channel, which means either a custom Streamlit component or a separate small voice service the Streamlit app talks to. This is the single item in the brief most likely to need an architecture decision from you before any code gets written. |
| 6 | Language/dialect/Hinglish detection | Regex-based Devanagari + Hinglish keyword heuristics in 2 places (`mas_engine.py`, `voice_assistant.py`) | Works for the common case; genuine dialect/code-switching detection would need an actual classifier, not more regex |
| 7 | Memory (conversation/citizen/officer/workflow) | Streamlit `st.session_state` only, no persistence across sessions | Real gap — needs a persistence layer |
| 8 | Multi-tier HITL + risk engine + knowledge sync | Single-tier SQLite queue: flag → `resolve_review(note)`. No risk scoring (only the confidence float already computed), no officer/senior tiers, no knowledge-base sync loop | Real gap, but the queue table and redaction logic are a usable foundation |
| 9 | Response validation (grounding/citation/hallucination/safety/compliance) | Output guardrail checks for leaked internal terms + domain-allowlist citation checks; no hallucination/grounding scoring | Partial — citation/domain checks exist, hallucination detection doesn't |
| 10 | Hybrid RAG (BM25 + vector + reranker + cache + query rewrite) | Ingestion (chunking, metadata, parent/child) is solid; retrieval is plain pgvector cosine search only | Retrieval-side gap specifically — don't rebuild ingestion |
| 11 | Workflow engine (approval/assignment/SLA/escalation) | Not present | Full build |
| 12 | Learning engine (resolved case → KB) | Not present | Full build |
| 13 | Observability (LangSmith/OTel/Prometheus/Grafana) | `print()` statements only | Full build |
| 14 | Security (RBAC/OAuth2/JWT/secrets manager) | Streamlit-secrets-or-env-var pattern, one shared `CSC_ADMIN_PASSWORD` for the admin page, domain allowlist, DPDP redaction | No RBAC, no per-user auth at all currently — worth flagging that this is a bigger decision (who are the user roles, how do they log in) before implementation |
| 15 | Performance targets (<500ms first token, <800ms first audio) | Not measured; no perf harness in repo | Need a benchmark harness before any target is meaningful |
| 16 | LLM Manager | **Real, tested, working** (§2) | Smallest gap in the list — extend, don't replace |
| 17 | Testing (unit/integration/voice/latency/RAG/security/regression) | 6 unit tests for the LLM manager only | Real gap everywhere else |

---

## 6. What I'd like your call on

Given the above, I think there are two responsible ways to proceed, and I don't want to guess which one you want:

1. **Cleanup pass first** (cheap, low-risk, ~1 session): fix the 5 stale docs to match reality, delete the dead `backend/voice/` stub and unused `styles.css` (or wire it up if you want the shared styling), consolidate the 5 copies of `_secret()`/`secret()` into one shared module, reconcile `.env.example` with `backend/secrets.toml.txt` into a single accurate template. This doesn't add features but it removes the exact kind of drift that caused this repo to need two "here's what's actually true" documents already.
2. **Pick one real module from §5** to build properly — end-to-end, tested, actually wired into `mas_engine.ask()` or the pages, not scaffolding. Realistic candidates given what already exists:
   - **Hybrid retrieval upgrade** (#10) — add BM25 + a reranker on top of the existing pgvector search and ingestion pipeline. Contained, testable, doesn't touch the UI.
   - **Multi-tier HITL** (#8) — extend the existing SQLite queue with risk scoring and an officer/senior approval chain. Contained, builds on real code.
   - **True multi-agent orchestration** (#1 + #4) — the biggest lift, and the one where I'd want to agree on scope (which of the 15 agents first, LangGraph vs. a lighter custom router) before writing code.
   - **Realtime voice** (#5) — the one that needs an architecture decision first (custom Streamlit component vs. companion service) before implementation even starts.

I'd suggest doing (1) regardless of what you pick for (2), since it's low-risk and prevents the next session (AI or human) from tripping over the same stale docs. Let me know how you'd like to sequence this.
