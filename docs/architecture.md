# CSC Mitra Architecture

> This document describes what's actually built and running. An earlier
> version of this file described an 8-agent LangGraph/ChromaDB system that
> was never implemented (see `CLEANUP_NOTES.md`). That vision is kept as a
> clearly-labeled roadmap at the bottom of this file instead of being
> presented as the current design — see `AUDIT_REPORT.md` for the full
> gap analysis against it.

## Overview

CSC Mitra is a **Streamlit application** (`app.py` → `pages/*.py`) that
provides an AI chat assistant, grievance filing, a knowledge base, and
role dashboards for Citizen Service Centre (CSC) workflows. It's a
single-process app — there is no separate API service, no microservices,
and no message queue.

## System Components

### 1. Frontend (Streamlit)

- **Entry points**: `app.py` (modern) or `streamlit_app.py` (legacy) — see
  `ENTRY_POINTS.md` for the difference.
- **Pages** (`pages/`): CSC Assistant, Grievance Redressal, Knowledge Base,
  VLE Dashboard, Officer Dashboard, Admin Dashboard.
- Each page reconstructs its own `sys.path` entries and imports
  `backend.*` modules directly — see "Import mechanics" below.

### 2. Backend (`backend/`)

Flat modules, not a package hierarchy (only `backend/llm/` is an actual
subpackage). The two modules that matter most:

- **`mas_engine.py`** — the orchestrator. Its one public function, `ask()`,
  runs a single pipeline (not a multi-agent graph — see "Naming note"
  below):
  ```
  query
    → try local built-in context (fast_mode only)
    → pgvector search (database.py)
    → fall back to built-in guide context if still empty
    → fall back to Tavily web search, allow-listed domains only,
      IF the user has given cloud-consent
    → compute a retrieval confidence score
    → if confidence is below threshold → route to HITL, return a
      local (non-LLM) answer with a "pending human review" note
    → if child/minor PII detected → route to HITL or refuse, depending
      on config
    → if no cloud consent → return a local (non-LLM) answer built
      directly from retrieved context, no LLM call at all
    → redact PII from query/context/history
    → call the LLM manager (backend/llm/) for a cloud answer
    → check the output for guardrail violations (leaked internal
      terms, disallowed URLs) → route to HITL if violated
    → polish formatting, append DPDP consent notice
    → return
  ```
- **`backend/llm/`** — config-driven LLM routing. YAML model catalog
  (`config/models.yaml`), per-model circuit breaker (`health.py`), rolling
  success-rate/latency telemetry from real call outcomes (`telemetry.py`),
  a scorer blending priority + reliability + speed + cost (`scoring.py`),
  and automatic fallback. See `backend/llm/README.md`.

Supporting modules: `database.py` (pgvector store), `knowledge.py` +
`document_extractors.py` (multi-format ingestion: PDF/DOCX/TXT/CSV/XLSX/
PPTX, with parent/child chunking), `crawler.py` (BFS crawl of allow-listed
domains), `guardrails.py` (domain allowlist), `hitl.py` (SQLite
human-review queue), `voice_assistant.py` (turn-based Whisper STT +
OpenAI TTS), `env_config.py` and `pii_patterns.py` (shared helpers used
across the modules above — see `CLEANUP_NOTES.md`, Session 3).

### 3. Knowledge Base

- **Ingestion**: URL crawl or file upload via the Knowledge Base page
  (admin-gated), processed by `knowledge.py` — recursive parent/child
  chunking, per-chunk metadata, document IDs.
- **Storage**: **PostgreSQL + pgvector** via raw `psycopg2` — *not*
  ChromaDB, despite `chromadb` still being listed in `requirements.txt`
  (unused; see `CLEANUP_NOTES.md`).
- **Embeddings**: OpenAI `text-embedding-3-small` — *not* BGE.
- **Retrieval**: plain cosine-distance vector search (`ORDER BY embedding
  <-> %s::vector`). No BM25, no reranker, no semantic cache, no query
  rewrite yet — see `AUDIT_REPORT.md` §5 for that gap.
- **Formats**: PDF, DOCX, TXT, CSV, XLSX, PPTX, and crawled URLs.

### 4. Database

- **PostgreSQL** (Neon or Supabase, pooled connection) — vector search
  (`documents`, `csc_knowledge` tables) via `database.py`.
- **SQLite** — the HITL human-review queue (`hitl.py`), a separate local
  file, not Postgres.
- There is no separate ChromaDB, no Redis, no message queue.

### 5. AI/LLM stack

- **LLMs**: routed by `backend/llm/` across Groq, Gemini, OpenRouter
  (including free-tier models), HuggingFace Router, and Grok — see
  `backend/llm/config/models.yaml` for the live catalog. Not hardcoded to
  OpenAI GPT-4 or Cohere.
- **Embeddings**: OpenAI `text-embedding-3-small`.
- **Orchestration**: a single Python function (`mas_engine.ask()`), not
  LangGraph. `langgraph` is listed in `requirements.txt` but unused.

## Naming note: "mas_engine" is not a multi-agent system

The file is named `mas_engine.py` (multi-agent system engine) but contains
one 1000+-line procedural module with ~35 flat functions and a single
public entry point, `ask()`. There is no `backend/agents/` package, no
agent-to-agent communication, and no orchestrator that routes between
independently-reasoning agents. It's a real, working retrieval → guardrail
→ HITL → LLM pipeline — just not a multi-agent one. See
`AUDIT_REPORT.md` §3 if you're deciding whether to actually build agent
decomposition.

## Import mechanics

`app.py` puts the repo root on `sys.path`. `streamlit_app.py` puts both
the repo root and its parent on `sys.path`. Each file under `pages/`
independently reconstructs and inserts both the repo root and `backend/`
onto `sys.path`. Because of this, `backend/mas_engine.py` and its sibling
modules import each other as flat modules (`from database import
vector_search`), not as `backend.database`, and several pages defensively
try both import forms. It works, but it's fragile — see `AUDIT_REPORT.md`
§4.5.

## Deployment

- **Streamlit Cloud** (see `DEPLOYMENT.md`): push to GitHub, point the
  app at `app.py`, configure secrets via the Streamlit Cloud UI using
  `backend/secrets.toml.txt` as the template.
- **Docker** (see `backend/Dockerfile`): single-container, runs
  `streamlit run app.py`.
- No Kubernetes, no separate API gateway, no horizontal scaling — this is
  a single-process deployment today.

## Data flow

### Chat / service query
1. User submits a query on the CSC Assistant page.
2. `mas_engine.ask()` runs the pipeline described above.
3. Response (with source citations / official URLs where available) is
   displayed in the chat UI.

### Document ingestion (admin only)
1. Admin uploads a document or URL via the Knowledge Base page.
2. `document_extractors.py` extracts text (format-specific).
3. `knowledge.py` performs parent/child recursive chunking.
4. `database.py` embeds each chunk (OpenAI) and stores it in Postgres/pgvector.
5. Available for retrieval on the next `vector_search()` call.

### Grievance filing
1. Citizen submits a complaint via the Grievance Redressal page.
2. Stored (see `pages/2_Grievance_Redressal.py` for the current storage
   mechanism — there is no separate ticket/SLA/assignment engine yet;
   that's listed as a gap in `AUDIT_REPORT.md` §5, item #11).

---

## Roadmap (not built — see AUDIT_REPORT.md for the full gap analysis)

The items below describe a larger enterprise-scale vision that has been
proposed for this repo more than once but never implemented. Keeping them
here, clearly separated from the "what's actually built" sections above,
so the vision isn't lost — but so nobody mistakes it for current state
again either:

- True multi-agent orchestration (LangGraph or similar), with independently
  reasoning agents for intent, service discovery, eligibility, document
  verification, compliance, workflow guidance, and grievance handling.
- Hybrid retrieval: BM25 + vector + cross-encoder reranking + semantic
  cache + query rewrite, on top of the ingestion pipeline that already
  exists.
- Multi-tier HITL with risk scoring, officer/senior approval chains, and
  a resolved-case → knowledge-base learning loop.
- A real workflow engine (ticket assignment, SLA tracking, escalation)
  for the grievance flow.
- Real-time streaming voice (VAD, barge-in, no push-to-talk) — this
  specifically needs an architecture decision first, since Streamlit's
  rerun-per-interaction model doesn't support persistent bidirectional
  audio without a custom component or a companion service.
- Observability (structured logging, tracing, metrics), RBAC/OAuth2, and
  a benchmark harness for the sub-second latency targets that have been
  proposed.
