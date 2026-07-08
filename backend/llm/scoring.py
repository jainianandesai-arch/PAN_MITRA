"""
Scores each available candidate model so the router can pick the best one,
instead of always trying providers in a fixed hardcoded order.

Score = priority_weight  * rank_score          (position in routing.yaml — the cold-start prior)
      + reliability_weight * success_rate       (from real telemetry; neutral 0.7 prior if no data yet)
      + speed_weight     * speed_score           (faster average latency scores higher; neutral if no data)
      + cost_weight      * cost_score            (free models score higher than paid ones)

Weights are intentionally simple and adjustable in one place. This is not
claiming to be a rigorously tuned bandit algorithm — it's a transparent,
explainable heuristic that improves over the original "always try in the
same fixed order" behavior by actually reacting to observed failures and
latency, while still respecting configured priority as a sane prior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .health import HealthMonitor
from .registry import ModelSpec
from .telemetry import TelemetryRecorder

WEIGHT_PRIORITY = 0.4
WEIGHT_RELIABILITY = 0.35
WEIGHT_SPEED = 0.15
WEIGHT_COST = 0.10

NEUTRAL_SUCCESS_RATE = 0.7  # optimistic-but-cautious prior for models with no telemetry yet
LATENCY_SCALE_MS = 8000.0  # latency at/above this is treated as "slow" (score -> 0)


@dataclass
class ScoredCandidate:
    spec: ModelSpec
    score: float
    reason: dict


def _rank_score(rank: int, total: int) -> float:
    if total <= 1:
        return 1.0
    return 1.0 - (rank / (total - 1))


def _speed_score(avg_latency_ms) -> float:
    if avg_latency_ms is None:
        return 0.5  # neutral
    return max(0.0, 1.0 - min(avg_latency_ms, LATENCY_SCALE_MS) / LATENCY_SCALE_MS)


def _cost_score(free: bool) -> float:
    return 1.0 if free else 0.3


def rank_candidates(
    specs: List[ModelSpec],
    health: HealthMonitor,
    telemetry: TelemetryRecorder,
) -> List[ScoredCandidate]:
    """
    Filters out unavailable (no key) and open-circuit (unhealthy) models,
    scores the rest, and returns them sorted best-first.
    """
    usable = [s for s in specs if s.available and health.is_available(s.id)]

    scored: List[ScoredCandidate] = []
    total = len(usable)
    for rank, spec in enumerate(usable):
        stats = telemetry.stats(spec.id)
        success_rate = stats["success_rate"] if stats["success_rate"] is not None else NEUTRAL_SUCCESS_RATE
        speed = _speed_score(stats["avg_latency_ms"])
        cost = _cost_score(spec.free)
        rank_component = _rank_score(rank, total)

        score = (
            WEIGHT_PRIORITY * rank_component
            + WEIGHT_RELIABILITY * success_rate
            + WEIGHT_SPEED * speed
            + WEIGHT_COST * cost
        )

        scored.append(
            ScoredCandidate(
                spec=spec,
                score=score,
                reason={
                    "rank_component": round(rank_component, 3),
                    "success_rate": round(success_rate, 3),
                    "speed_score": round(speed, 3),
                    "cost_score": round(cost, 3),
                    "sample_size": stats["sample_size"],
                },
            )
        )

    scored.sort(key=lambda c: c.score, reverse=True)
    return scored
