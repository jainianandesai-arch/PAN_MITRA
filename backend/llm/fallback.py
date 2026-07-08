"""
Walks a ranked candidate list, calling each in turn until one produces a
usable answer. Two distinct failure modes are tracked separately, because
they mean different things for health scoring:

  - "error"    — the call itself failed (network/timeout/HTTP error). This
                 counts against the model's health circuit breaker.
  - "rejected" — the call succeeded but the caller's own validator rejected
                 the content (e.g. it failed a guardrail check). This does
                 NOT count against health — the model is reachable and
                 working, the *answer* just wasn't acceptable this time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .health import HealthMonitor, default_health_monitor
from .providers import PROVIDER_CALLERS
from .scoring import ScoredCandidate
from .telemetry import CallOutcome, TelemetryRecorder, default_telemetry


class AllProvidersFailedError(RuntimeError):
    def __init__(self, task: str, attempts: List[str]):
        self.task = task
        self.attempts = attempts
        super().__init__(
            f"All {len(attempts)} candidate model(s) failed or were unavailable for task "
            f"'{task}': {', '.join(attempts) or '(no candidates configured/available)'}"
        )


@dataclass
class GenerationResult:
    content: str
    model_id: str
    provider: str
    latency_ms: float
    attempts: List[str]


def run(
    task: str,
    candidates: List[ScoredCandidate],
    messages: List[dict],
    temperature: float,
    max_tokens: int,
    validate_fn: Optional[Callable[[str], bool]] = None,
    health: HealthMonitor = default_health_monitor,
    telemetry: TelemetryRecorder = default_telemetry,
) -> GenerationResult:
    attempted: List[str] = []

    for candidate in candidates:
        spec = candidate.spec
        attempted.append(spec.id)
        caller = PROVIDER_CALLERS.get(spec.provider)
        if caller is None:
            continue

        try:
            result = caller(spec, messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as exc:
            health.record_failure(spec.id)
            telemetry.record(
                CallOutcome(
                    model_id=spec.id, task=task, success=False,
                    latency_ms=0.0, reason=type(exc).__name__,
                )
            )
            continue

        if not result.content:
            health.record_failure(spec.id)
            telemetry.record(
                CallOutcome(
                    model_id=spec.id, task=task, success=False,
                    latency_ms=result.latency_ms, reason="empty_response",
                )
            )
            continue

        if validate_fn is not None and not validate_fn(result.content):
            # reachable and working — just not an acceptable answer this time.
            telemetry.record(
                CallOutcome(
                    model_id=spec.id, task=task, success=True,
                    latency_ms=result.latency_ms, reason="rejected_by_validator",
                )
            )
            continue

        health.record_success(spec.id)
        telemetry.record(
            CallOutcome(model_id=spec.id, task=task, success=True, latency_ms=result.latency_ms)
        )
        return GenerationResult(
            content=result.content,
            model_id=spec.id,
            provider=spec.provider,
            latency_ms=result.latency_ms,
            attempts=attempted,
        )

    raise AllProvidersFailedError(task, attempted)
