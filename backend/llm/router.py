"""
TaskAnalyzer: a lightweight, honest heuristic classifier — not a trained
model. It only needs to pick a *task category* that exists in routing.yaml;
callers can also just pass the task explicitly (mas_engine already knows
whether it's answering a RAG query or a voice turn) and skip classification
entirely. The heuristic exists for callers that only have a raw query string.

ModelRouter: ties registry + health + telemetry + scoring together to
produce a ranked candidate list for a given task.
"""

from __future__ import annotations

from typing import List, Optional

from .health import HealthMonitor, default_health_monitor
from .registry import ModelRegistry, ModelSpec
from .scoring import ScoredCandidate, rank_candidates
from .telemetry import TelemetryRecorder, default_telemetry
from .user_override import get_override

_TRANSLATION_HINTS = ("translate", "अनुवाद", "meaning of", "in hindi", "in english")
_CLASSIFICATION_HINTS = ("classify", "category of", "which category")


class TaskAnalyzer:
    def classify(self, query: str, fast_mode: bool = False) -> str:
        text = (query or "").lower()
        if any(hint in text for hint in _TRANSLATION_HINTS):
            return "translation"
        if any(hint in text for hint in _CLASSIFICATION_HINTS):
            return "classification"
        return "rag_answer"


class ModelRouter:
    def __init__(
        self,
        registry: ModelRegistry,
        health: HealthMonitor = default_health_monitor,
        telemetry: TelemetryRecorder = default_telemetry,
    ):
        self.registry = registry
        self.health = health
        self.telemetry = telemetry

    def candidates(self, task: str, fast_mode: bool = False) -> List[ScoredCandidate]:
        model_ids = self.registry.candidates_for_task(task, fast_mode=fast_mode)
        specs: List[ModelSpec] = [self.registry.resolve(mid) for mid in model_ids]
        ranked = rank_candidates(specs, self.health, self.telemetry)

        preferred_id = get_override().get("model_id")
        if preferred_id:
            # Stable sort: the preferred model (if it's a valid, available
            # candidate for this task) moves to the front; scoring order
            # among the rest is untouched.
            ranked = sorted(ranked, key=lambda c: c.spec.id != preferred_id)
        return ranked

    def best(self, task: str, fast_mode: bool = False) -> Optional[ScoredCandidate]:
        ranked = self.candidates(task, fast_mode=fast_mode)
        return ranked[0] if ranked else None
