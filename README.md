# PAN Mitra

A single-purpose Streamlit application that guides citizens/VLEs end-to-end
through PAN card services — New PAN, Correction, Reprint, and Instant e-PAN —
using a **LangGraph tool-calling agent**, with local request tracking, officer
escalation, a live pipeline view, and analytics.

> This was rebuilt from a broader multi-service "CSC Mitra AI" platform
> (chat assistant, grievance filing, general knowledge base, role dashboards)
> into a focused PAN application. See `CLEANUP_NOTES.md` for the full history,
> including what was removed and why.

## What this actually is

- A **Streamlit** single-page app (`app.py` → `streamlit_app.py`, no
  `pages/` multipage folder — one entry point, nothing else to navigate to).
- The core is `backend/pan_graph.py`: a real LangGraph **agent ⇄ tools loop**
  (not a fixed pipeline). The LLM decides which of 6 Python tool functions to
  call each turn — `lookup_pan_guidance`, `check_required_documents`,
  `check_eligibility`, `create_tracking_record`, `escalate_to_officer`,
  `get_application_status`. Deterministic, non-LLM safety gates (PII
  detection, low-confidence escalation) run *before* the agent loop, since
  those can't be left to model discretion.
- Local request tracking is plain SQLite (`backend/pan_tracking.py`), and
  officer escalation reuses the existing HITL queue (`backend/hitl.py`).
- LLM calls go through `backend/llm/` — a config-driven router (YAML model
  catalog, health/circuit-breaker, telemetry-based scoring, automatic
  fallback across Groq/Gemini/OpenRouter/HuggingFace/Grok/OpenAI/Anthropic).
  An **AI Provider** picker in the Settings tab lets you pin one provider +
  key and test the connection live, instead of guessing which of several
  configured providers actually works.
- **No voice** — the original voice feature (OpenAI Whisper STT + TTS) was
  removed; it was confirmed non-functional in this environment before removal
  (`whisper_stt_enabled() == False`, live TTS call failed).

## Tabs

- 🆕 **New Request** — pick a PAN service (or let the agent detect it),
  describe the need, submit. Never accepts Aadhaar/PAN/OTP — blocked before
  anything is stored.
- 📋 **Tracked Requests** — local request history with status progression.
- ⚠️ **Escalated to Officer** — low-confidence or agent-initiated
  escalations, reusing the HITL review queue.
- 🕸️ **Pipeline View** — the LangGraph agent's actual node sequence and
  tool calls from the last run, plus the raw graph definition.
- 📊 **Analytics** — status/service-type breakdown.
- ⚙️ **Settings** — AI provider picker, appearance, backend status.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your own keys — do NOT commit this file
streamlit run app.py
```

At least one LLM provider key is required (`GROQ_API_KEY`, `GEMINI_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. — see `.env.example`). If none are
configured or all fail, requests still work by falling back to the built-in
structured guidance content — the agent loop just doesn't run.

## LLM Manager (config-driven model routing)

`backend/llm/` loads the model catalog from YAML, tracks per-model health
(circuit breaker) and telemetry (rolling success rate / latency) from actual
call outcomes, scores candidates instead of always trying the same order, and
falls back automatically on failure or guardrail rejection. See
`backend/llm/README.md` for usage and how to add a model, and the Settings
tab's AI Provider section to pin/test a specific provider from the UI.
`backend/tests/test_llm_manager.py` (6 tests, no network/API keys required)
covers the routing/fallback/circuit-breaker logic.

## History

`AUDIT_REPORT.md` and `CLEANUP_NOTES.md` document the repo's prior life as
the general-purpose "CSC Mitra AI" platform, including a full audit of what
was solid vs. dead code, and the sessions that consolidated duplicated
helpers, fixed stale docs, and (this session) rebuilt PAN into an end-to-end
LangGraph feature and rebranded the whole app around it.
