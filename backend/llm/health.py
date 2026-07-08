"""
Per-model circuit breaker.

Without this, a model that's rate-limited or down gets retried on *every*
incoming request, adding latency for every user until it happens to recover.
The breaker opens after consecutive failures and stops offering that model
as a candidate until a cooldown elapses, then allows one probe request
(half-open) to test recovery.

State is process-global (module-level), not per-session: provider health is
infrastructure state shared by all users of this server process, not a
per-user concern. It intentionally does not persist across restarts —
on restart we want to give every provider a fresh chance.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 120.0


@dataclass
class _ModelHealth:
    consecutive_failures: int = 0
    opened_at: float = 0.0
    last_success_at: float = 0.0
    last_failure_at: float = 0.0

    @property
    def state(self) -> str:
        if self.consecutive_failures < FAILURE_THRESHOLD:
            return "closed"
        if time.time() - self.opened_at >= COOLDOWN_SECONDS:
            return "half_open"
        return "open"


class HealthMonitor:
    """Thread-safe, process-wide health tracker keyed by model id."""

    def __init__(self):
        self._lock = threading.Lock()
        self._state: Dict[str, _ModelHealth] = {}

    def _get(self, model_id: str) -> _ModelHealth:
        if model_id not in self._state:
            self._state[model_id] = _ModelHealth()
        return self._state[model_id]

    def is_available(self, model_id: str) -> bool:
        """False only for models in an OPEN circuit (recently failed repeatedly, still cooling down)."""
        with self._lock:
            return self._get(model_id).state != "open"

    def record_success(self, model_id: str) -> None:
        with self._lock:
            health = self._get(model_id)
            health.consecutive_failures = 0
            health.last_success_at = time.time()

    def record_failure(self, model_id: str) -> None:
        with self._lock:
            health = self._get(model_id)
            health.consecutive_failures += 1
            health.last_failure_at = time.time()
            if health.consecutive_failures == FAILURE_THRESHOLD:
                health.opened_at = time.time()
            elif health.consecutive_failures > FAILURE_THRESHOLD:
                # still failing during/after a half-open probe — reopen the cooldown window
                health.opened_at = time.time()

    def snapshot(self) -> Dict[str, dict]:
        """For a health/telemetry dashboard."""
        with self._lock:
            return {
                model_id: {
                    "state": h.state,
                    "consecutive_failures": h.consecutive_failures,
                    "last_success_at": h.last_success_at,
                    "last_failure_at": h.last_failure_at,
                }
                for model_id, h in self._state.items()
            }


# Single process-wide instance — health is shared infrastructure state.
default_health_monitor = HealthMonitor()
