"""
Generic provider for any endpoint implementing the OpenAI /chat/completions
schema (Groq, Gemini's OpenAI-compat endpoint, OpenRouter, HF Router, x.ai,
and any future addition of the same shape). This is the direct extraction
of the request-building logic that used to live inline in mas_engine.py's
_llm_answer / _chat_endpoint, now reusable for any model in the registry.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

import requests

from ..registry import ModelSpec


@dataclass
class ProviderResult:
    content: str
    latency_ms: float
    raw_usage: Optional[dict] = None


def _chat_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def call(
    spec: ModelSpec,
    messages: List[dict],
    temperature: float = 0.2,
    max_tokens: int = 1200,
) -> ProviderResult:
    payload = {
        "model": spec.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {spec.api_key}",
        "Content-Type": "application/json",
        "User-Agent": "CSC-AI-Assistant/1.0",
    }
    if "openrouter.ai" in spec.base_url:
        headers["X-Title"] = "CSC AI Assistant"

    started = time.monotonic()
    response = requests.post(
        _chat_endpoint(spec.base_url),
        json=payload,
        headers=headers,
        timeout=spec.timeout,
    )
    latency_ms = (time.monotonic() - started) * 1000
    response.raise_for_status()
    data = response.json()

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        content = ""

    return ProviderResult(content=content, latency_ms=latency_ms, raw_usage=data.get("usage"))
