# LLM Manager

Config-driven model routing with health tracking, telemetry-based scoring,
and automatic fallback. Replaces the old hardcoded, statically-ordered
provider list that used to live in `mas_engine.py` (`_provider_chain`).

## Why this exists

The original code tried providers in the same fixed order on every single
request (Groq → Gemini → OpenRouter → HuggingFace → Grok, or a different
fixed order for voice/fast_mode), regardless of whether a provider was
currently down, rate-limited, or slow. A dead provider got retried on every
request forever, adding latency for every user.

This package instead:

1. **Loads the model catalog from YAML** (`config/models.yaml`), not Python —
   add, remove, or reorder models without a code change.
2. **Tracks real health per model** (`health.py`) — a circuit breaker opens
   after 3 consecutive failures and stops offering that model as a candidate
   for a 2-minute cooldown, then probes it once (half-open) to check recovery.
3. **Tracks real telemetry per model** (`telemetry.py`) — rolling success
   rate and average latency over the last 50 calls, computed from actual
   outcomes, not assumed.
4. **Scores candidates** (`scoring.py`) combining configured priority order
   (used as the cold-start prior), live reliability, live speed, and cost
   (free models preferred over paid ones) — see the module docstring for the
   exact weights.
5. **Falls back automatically** (`fallback.py`) — tries the best-scored
   available candidate, and on failure *or* on content-validator rejection
   (e.g. a guardrail check), moves to the next one. A validator rejection
   does NOT count against the model's health — it means the model responded
   fine, the content just wasn't acceptable that time.

## Usage

```python
from llm import default_manager as llm_manager

result = llm_manager.generate(
    messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
    task="rag_answer",       # or omit `task` and pass query_for_classification=... instead
    fast_mode=False,
    temperature=0.2,
    max_tokens=1200,
    validate_fn=my_guardrail_check,  # optional: str -> bool
)

result.content     # the answer text
result.model_id    # which model actually produced it, e.g. "openrouter_free"
result.latency_ms  # latency of the winning call
result.attempts    # every model id tried, in order, including failed ones
```

If every candidate fails or is unavailable, `generate()` raises
`llm.AllProvidersFailedError` — catch it and fall back to your own
non-AI path, same as the old code did when the for-loop exhausted itself.

## Adding a model

All current models speak the OpenAI-compatible `/chat/completions` schema,
so adding one is just a new entry in `config/models.yaml`:

```yaml
models:
  my_new_model:
    provider: openai_compatible
    base_url_env: MY_MODEL_BASE_URL
    base_url_default: https://example.com/v1
    key_env: [MY_MODEL_API_KEY]
    model_env: MY_MODEL_NAME
    model_default: some/model-id
    timeout_env: LLM_TIMEOUT_SECONDS
    timeout_default: 45.0
    context_length: 32000
    free: true
    tags: [general, rag_answer]
```

Then add its id to whichever task lists in `config/routing.yaml` should be
allowed to use it. No Python changes needed. If a model needs a genuinely
different calling convention (not OpenAI-schema), set `provider: litellm`
instead (requires `pip install litellm`) or add a new module under
`providers/` and register it in `providers/__init__.py`.

## Inspecting live state

```python
llm_manager.health_snapshot()
# {"openrouter_free": {"state": "closed", "consecutive_failures": 0,
#                       "telemetry": {"sample_size": 12, "success_rate": 0.92, "avg_latency_ms": 640.5}},
#  ...}
```

Useful for wiring into an admin/ops dashboard page. Raw call-level history
is also appended (best-effort) to `data/telemetry.jsonl` if you want to
build real analytics on top of it later.

## What this deliberately does NOT do

- No real task classifier model — `TaskAnalyzer` is a small keyword
  heuristic. If you always know the task at the call site (mas_engine does),
  pass `task=` explicitly and skip classification.
- No semantic cache — `cache.py` is not implemented in this pass; adding
  one is a reasonable next step (hash-of-prompt → response, with TTL) but
  wasn't built here since there's no evidence yet of repeated identical
  prompts in this app's traffic to justify it.
- No fabricated benchmark numbers. `scoring.py`'s weights are a documented,
  adjustable heuristic — not a tuned bandit algorithm — because there's no
  production traffic yet to tune against.

## Tests

```bash
cd backend
pip install pytest pyyaml
python -m pytest tests/test_llm_manager.py -v
```

All 6 tests run against a monkeypatched provider — no network calls, no
API keys required — and verify: registry key resolution, candidate
filtering, fallback-on-exception, circuit-breaker opening, validator
rejection *not* penalizing health, and the all-failed error path.
