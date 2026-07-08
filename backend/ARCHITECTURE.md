# Backend Architecture

This file used to be a module docstring describing RAG services
(`backend/services/`), a multi-agent system (`backend/agents/`), workflow
engines (`backend/workflows/`), and LangGraph integration
(`backend/graph/`). None of those packages back real, imported code —
they were confirmed by grep to have zero references from anything that
actually runs, and were removed in a prior cleanup session (see
`../CLEANUP_NOTES.md`). This file now describes what's actually here.

## What's actually in `backend/`

Flat modules directly under `backend/`, plus one real subpackage
(`backend/llm/`). Nothing else is nested.

| Module | Role |
|---|---|
| `mas_engine.py` | Main orchestrator. `ask(query, ...)` runs retrieval → confidence scoring → HITL routing → PII redaction → LLM call → output guardrail → DPDP notice, as one function. Despite the filename, this is **not** a multi-agent system — see `../docs/architecture.md`. |
| `llm/` | The one real subpackage. Config-driven LLM routing: YAML model catalog, per-model circuit breaker, telemetry-based scoring, automatic fallback. See `llm/README.md`. |
| `database.py` | Postgres + pgvector store and cosine-similarity search (`psycopg2`, not ChromaDB). |
| `knowledge.py` | Ingestion: parent/child recursive chunking, metadata, document IDs. |
| `document_extractors.py` | PDF/DOCX/TXT/CSV/XLSX/PPTX → plain text. |
| `crawler.py` | BFS crawler restricted to allow-listed domains. |
| `guardrails.py` | Domain allowlist (70+ official CSC/government domains) and URL validation. |
| `hitl.py` | SQLite-backed human-review queue (queue, list pending, resolve). |
| `voice_assistant.py` | OpenAI Whisper STT + OpenAI TTS, turn-based (record → transcribe → speak), not streaming. |
| `env_config.py` | Shared secrets/env-var accessor (`st.secrets` first, then `os.getenv`), used by every module above instead of each defining its own copy. |
| `pii_patterns.py` | Shared PII detection/redaction patterns (Aadhaar, PAN, email, phone, IFSC, account number, DOB), used by both `mas_engine.py` and `hitl.py`. |
| `adaptive_response.py` | Response-mode detection and profile context lookup. |
| `builtin_guides.py`, `core_knowledge_pack.py` | Hand-written offline fallback content, used when pgvector search comes up empty. |
| `service_catalog.py` | Official-URL lookup by keyword, used for citation/suggestion. |
| `tavily_search.py` | Web-search fallback, restricted to allow-listed domains, gated on user cloud-consent. |
| `tests/test_llm_manager.py` | 6 unit tests covering the LLM manager (registry, fallback, circuit breaker, validator rejection) — no network calls, no API keys required. |

## Import mechanics (worth knowing before adding a module)

`mas_engine.py` and its siblings import each other as flat modules
(`from database import vector_search`), not as `backend.database`. This
only works because `backend/` itself is put on `sys.path` by every
caller (`app.py`, `streamlit_app.py`, and each file under `../pages/`),
in addition to the repo root. If you add a new module under `backend/`
and want it importable from `mas_engine.py`, follow the same flat-import
convention the existing modules use — don't introduce `backend.<name>`
imports inside `backend/` itself, or you'll get an inconsistent mix like
the one already flagged in `AUDIT_REPORT.md` §4.5.

## Adding a genuinely new capability

If you're implementing something from `AUDIT_REPORT.md`'s gap list (a
real multi-agent split, hybrid retrieval, a workflow engine, etc.):
create the module, wire it into whatever actually calls it
(`mas_engine.ask()` or a specific page), and make sure `grep -rn
"module_name" backend/ pages/ app.py streamlit_app.py` shows real callers
before considering it done. That check is what would have caught the
scaffolding this file used to describe.
