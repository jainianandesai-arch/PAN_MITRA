"""
LLMManager — the single entry point the rest of the app talks to.

    manager = LLMManager()
    result = manager.generate(
        task="rag_answer",
        messages=[...],
        fast_mode=False,
        temperature=0.2,
        max_tokens=1200,
        validate_fn=my_guardrail_check,   # optional
    )
    result.content, result.model_id, result.latency_ms, result.attempts

This replaces a hardcoded, statically-ordered provider list with:
  registry (config-driven catalog) -> router (health + telemetry-aware scoring)
  -> fallback (try best-first, skip circuit-open/unavailable, retry on failure
     or guardrail rejection) -> GenerationResult.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from . import fallback
from .health import HealthMonitor, default_health_monitor
from .registry import ModelRegistry
from .router import ModelRouter, TaskAnalyzer
from .telemetry import TelemetryRecorder, default_telemetry


class LLMManager:
    def __init__(
        self,
        registry: Optional[ModelRegistry] = None,
        health: HealthMonitor = default_health_monitor,
        telemetry: TelemetryRecorder = default_telemetry,
    ):
        self.registry = registry or ModelRegistry()
        self.health = health
        self.telemetry = telemetry
        self.router = ModelRouter(self.registry, health=health, telemetry=telemetry)
        self.task_analyzer = TaskAnalyzer()

    def generate(
        self,
        messages: List[dict],
        task: Optional[str] = None,
        query_for_classification: Optional[str] = None,
        fast_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        validate_fn: Optional[Callable[[str], bool]] = None,
    ) -> fallback.GenerationResult:
        if task is None:
            task = self.task_analyzer.classify(query_for_classification or "", fast_mode=fast_mode)

        candidates = self.router.candidates(task, fast_mode=fast_mode)

        return fallback.run(
            task=task,
            candidates=candidates,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            validate_fn=validate_fn,
            health=self.health,
            telemetry=self.telemetry,
        )

    def health_snapshot(self) -> dict:
        """For an ops/health dashboard: current circuit state + rolling stats per model."""
        snapshot = self.health.snapshot()
        for model_id in self.registry.all_model_ids():
            snapshot.setdefault(model_id, {"state": "closed", "consecutive_failures": 0})
            snapshot[model_id]["telemetry"] = self.telemetry.stats(model_id)
        return snapshot


# Process-wide singleton for convenience — mirrors how the rest of the app
# (Streamlit, module-level state) already works. Callers that want isolation
# (e.g. tests) should construct their own LLMManager(registry=..., health=HealthMonitor(), ...).
default_manager = LLMManager()
