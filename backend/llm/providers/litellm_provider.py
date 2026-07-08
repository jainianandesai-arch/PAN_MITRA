"""
Optional LiteLLM-backed provider.

The generic openai_compatible provider covers every model currently in
models.yaml (they're all OpenAI-schema endpoints already). This module
exists for the case where you want to add a model that's easier to reach
through LiteLLM's unified interface (native SDKs, provider-specific auth
quirks, etc.) rather than hand-rolling another requests.post call.

litellm is intentionally NOT a hard dependency of this package — it's only
imported when a model in the registry is configured with `provider: litellm`.
Install it with: pip install litellm
"""

from __future__ import annotations

import time
from typing import List

from ..registry import ModelSpec
from .openai_compatible import ProviderResult


class LiteLLMNotInstalled(RuntimeError):
    pass


def call(
    spec: ModelSpec,
    messages: List[dict],
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> ProviderResult:
    try:
        import litellm
    except ImportError as exc:
        raise LiteLLMNotInstalled(
            f"Model '{spec.id}' is configured with provider: litellm but the "
            "litellm package is not installed. Run: pip install litellm"
        ) from exc

    started = time.monotonic()
    response = litellm.completion(
        model=spec.model,
        messages=messages,
        api_key=spec.api_key,
        api_base=spec.base_url or None,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=spec.timeout,
    )
    latency_ms = (time.monotonic() - started) * 1000

    content = (response["choices"][0]["message"]["content"] or "").strip()
    usage = getattr(response, "usage", None)

    return ProviderResult(content=content, latency_ms=latency_ms, raw_usage=usage)
