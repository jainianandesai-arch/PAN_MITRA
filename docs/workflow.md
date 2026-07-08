# CSC Mitra — Actual Query Workflow

> This document shows what actually happens when a query comes in, traced
> through `backend/mas_engine.py`'s `ask()` function. An earlier version
> of this file showed an 8-agent pipeline (Intent Agent → Service Discovery
> Agent → Eligibility Agent → Document Verification Agent → ...) with a
> ticket/SLA engine and OCR/compliance checks. None of that exists in the
> code — see `CLEANUP_NOTES.md` and `AUDIT_REPORT.md`. That aspirational
> version is kept, clearly labeled as a roadmap, in
> `docs/architecture.md`'s final section instead of being presented here
> as current behavior.

## The real pipeline (one function, `mas_engine.ask()`)

```
query
  │
  ├─ fast_mode? → try builtin_service_context() first (hand-written
  │                offline fallback content in builtin_guides.py)
  │
  ├─ vector_search(query)  — pgvector cosine search against ingested docs
  │
  ├─ still empty? → try builtin_service_context() again
  │
  ├─ still empty?
  │     ├─ no cloud consent  → refusal message + suggested official URLs
  │     └─ cloud consent     → Tavily web search, allow-listed domains only
  │
  ├─ compute retrieval confidence (keyword overlap + presence of an
  │   official URL in the retrieved context)
  │
  ├─ confidence < HITL_CONFIDENCE_THRESHOLD?
  │     → queue for human review, return a local (non-LLM) draft answer
  │       with a "this has been sent for review" note
  │
  ├─ child/minor PII detected alongside personal data?
  │     → queue for human review (or refuse, depending on
  │       HITL_ROUTE_SENSITIVE_QUERIES)
  │
  ├─ no cloud consent?
  │     → return a local (non-LLM) answer built directly from the
  │       retrieved context — no LLM call happens at all
  │
  ├─ redact PII from query, context, and conversation history
  │
  ├─ call the LLM manager (backend/llm/) — health-aware routing across
  │   configured providers, automatic fallback on failure
  │
  ├─ LLM answer received?
  │     ├─ output guardrail check (leaked internal terms, disallowed
  │     │   URLs) fails → queue for human review instead of returning it
  │     └─ passes → polish formatting, append DPDP consent notice, return
  │
  └─ LLM call failed entirely → return a local (non-LLM) fallback answer
```

## Worked example: "How do I register for PM-KISAN?"

1. `mas_engine.ask("How do I register for PM-KISAN?", cloud_consent=True)`
   is called from `pages/1_CSC_Assistant.py`.
2. `vector_search()` queries Postgres/pgvector for the closest-matching
   ingested chunks. If PM-KISAN documentation has been ingested via the
   Knowledge Base page, this returns real chunks (with `Source:` URLs);
   otherwise `builtin_service_context()` supplies a hand-written fallback
   (see `builtin_guides.py`).
3. Confidence is scored from keyword overlap between the query and the
   retrieved context, plus whether an official `pmkisan.gov.in`-family URL
   is present.
4. Assuming confidence clears the threshold and no child-PII is detected:
   the query, context, and recent chat history are PII-redacted, then sent
   to the LLM manager, which tries the configured provider chain (Groq →
   Gemini → ... for fast mode) until one succeeds.
5. The answer is checked for leaked internal terms / disallowed URLs. If
   clean, it's formatted (structured with headings pulled from the
   retrieved context — see `_structured_answer()`), a DPDP notice is
   appended, and it's returned to the page for display.
6. If nothing was ingested and no built-in fallback matches the query, and
   the user hasn't consented to cloud processing, the response is a
   refusal with suggested official URLs (`suggested_csc_urls()`) rather
   than a guess.

## Worked example: a query containing personal data

1. User asks something like "my Aadhaar is 1234 5678 9012, is my PM-KISAN
   application approved?"
2. `_has_personal_data()` (via `backend/pii_patterns.py`) flags the
   Aadhaar-shaped number.
3. If a child/minor marker is *also* present in the text (e.g. mentions of
   "my child's school", "guardian"), the query is routed to the SQLite
   HITL queue (`backend/hitl.py`) instead of going to an LLM, unless
   `DPDP_ALLOW_CHILD_DATA_CLOUD` is explicitly enabled.
4. Otherwise, the Aadhaar number is redacted to `[REDACTED_AADHAAR]`
   before anything is sent to a cloud LLM — the model never sees the raw
   number.
5. Separately, if this query gets queued for human review for any reason,
   the version written to the SQLite queue is redacted with a generic
   `[REDACTED_PERSONAL_DATA]` placeholder rather than the typed one (a
   human reviewer doesn't need to know it was specifically an Aadhaar
   number, just that something was masked) — see `backend/pii_patterns.py`.

## Grievance filing (current state)

`pages/2_Grievance_Redressal.py` handles complaint submission today. There
is **no separate ticket engine, SLA engine, or officer-assignment logic**
yet — see `AUDIT_REPORT.md` §5, item #11, and `docs/architecture.md`'s
roadmap section for what a real workflow engine would need to add.

## Document ingestion (current state)

`pages/3_Knowledge_Base.py` (admin-gated) → `knowledge.py`:
recursive parent/child chunking → `database.py`: OpenAI embedding +
Postgres/pgvector storage. No OCR step currently — scanned/image-only PDFs
won't extract text via `document_extractors.py`'s `extract_pdf()`.

## What the aspirational multi-agent workflow would need

If you want the original vision — Intent Agent routing to Service
Discovery / Eligibility / Document Verification / Compliance agents, with
a Fusion Agent synthesizing results — that's a real build, not a
rename of what exists. See `docs/architecture.md`'s roadmap section and
`AUDIT_REPORT.md` §5 for the gap analysis and a suggested phasing.
