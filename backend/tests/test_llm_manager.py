"""
Unit tests for backend/llm/. No network calls, no API keys needed — the
provider call is monkeypatched so these test routing/fallback/health logic
in isolation.

Run with:  cd backend && python -m pytest tests/test_llm_manager.py -v
(requires: pip install pytest pyyaml)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from llm.health import HealthMonitor
from llm.manager import LLMManager
from llm.providers import PROVIDER_CALLERS
from llm.providers.openai_compatible import ProviderResult
from llm.registry import ModelRegistry
from llm.telemetry import TelemetryRecorder


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "sk-test-groq")
    monkeypatch.setenv("HF_TOKEN", "hf-test")


@pytest.fixture
def fresh_manager():
    return LLMManager(
        registry=ModelRegistry(),
        health=HealthMonitor(),
        telemetry=TelemetryRecorder(),
    )


@pytest.fixture
def patch_provider():
    original = PROVIDER_CALLERS["openai_compatible"]
    yield lambda fn: PROVIDER_CALLERS.__setitem__("openai_compatible", fn)
    PROVIDER_CALLERS["openai_compatible"] = original


def test_registry_resolves_only_models_with_keys(keys):
    registry = ModelRegistry()
    spec = registry.resolve("openrouter_free")
    assert spec.available is True

    unresolved = registry.resolve("grok")  # no GROK_API_KEY / XAI_API_KEY set
    assert unresolved.available is False


def test_unavailable_models_are_never_candidates(keys, fresh_manager):
    candidates = fresh_manager.router.candidates("rag_answer", fast_mode=False)
    ids = [c.spec.id for c in candidates]
    assert "grok" not in ids  # no key configured
    assert "gemini_flash" not in ids  # no key configured
    assert "openrouter_free" in ids


def test_falls_back_to_next_candidate_on_exception(keys, fresh_manager, patch_provider):
    def flaky(spec, messages, temperature, max_tokens):
        if spec.id == "huggingface_router":
            raise TimeoutError("simulated timeout")
        return ProviderResult(content=f"ok from {spec.id}", latency_ms=5.0)

    patch_provider(flaky)

    result = fresh_manager.generate(messages=[{"role": "user", "content": "hi"}], task="rag_answer")
    assert result.model_id != "huggingface_router"
    assert "huggingface_router" in result.attempts  # it was tried
    assert result.content.startswith("ok from")


def test_circuit_breaker_opens_after_repeated_failures(monkeypatch, fresh_manager, patch_provider):
    # Isolate a single candidate: with only HF_TOKEN set, huggingface_router
    # is the *only* available model for this task, so fallback has no other
    # healthy candidate to satisfy the request with — it must keep retrying
    # this one across calls, letting failures actually accumulate.
    monkeypatch.setenv("HF_TOKEN", "hf-test")

    def always_fails(spec, messages, temperature, max_tokens):
        raise ConnectionError("down")

    patch_provider(always_fails)

    from llm.fallback import AllProvidersFailedError

    for _ in range(3):
        with pytest.raises(AllProvidersFailedError):
            fresh_manager.generate(messages=[{"role": "user", "content": "hi"}], task="rag_answer")

    assert fresh_manager.health.is_available("huggingface_router") is False
    candidates = fresh_manager.router.candidates("rag_answer", fast_mode=False)
    assert candidates == []  # the only candidate is now circuit-open


def test_validator_rejection_does_not_penalize_health(keys, fresh_manager, patch_provider):
    def leaky_then_clean(spec, messages, temperature, max_tokens):
        if spec.id == "openrouter_free":
            return ProviderResult(content="internal embedding score leaked", latency_ms=1.0)
        return ProviderResult(content="clean answer", latency_ms=1.0)

    patch_provider(leaky_then_clean)

    result = fresh_manager.generate(
        messages=[{"role": "user", "content": "hi"}],
        task="rag_answer",
        validate_fn=lambda text: "embedding" not in text.lower(),
    )

    assert result.model_id != "openrouter_free"
    snapshot = fresh_manager.health.snapshot().get("openrouter_free", {})
    assert snapshot.get("consecutive_failures", 0) == 0  # not penalized


def test_all_providers_failed_raises(keys, fresh_manager, patch_provider):
    from llm.fallback import AllProvidersFailedError

    def always_fails(spec, messages, temperature, max_tokens):
        raise ConnectionError("down")

    patch_provider(always_fails)

    with pytest.raises(AllProvidersFailedError):
        fresh_manager.generate(messages=[{"role": "user", "content": "hi"}], task="rag_answer")
