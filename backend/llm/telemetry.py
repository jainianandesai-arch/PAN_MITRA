"""
Records actual call outcomes so routing decisions can be based on real,
observed behavior instead of static config alone.

Two layers:
  1. An in-memory rolling window per model (last N calls) used by scoring.py —
     cheap, always available, resets on process restart.
  2. A best-effort append-only JSONL log on disk, for anyone who wants to
     build a benchmarking dashboard on top of real history. Writing to disk
     is wrapped in try/except: telemetry must never break a live request.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Optional

_LOG_PATH = Path(__file__).parent / "data" / "telemetry.jsonl"
_WINDOW_SIZE = 50


@dataclass
class CallOutcome:
    model_id: str
    task: str
    success: bool
    latency_ms: float
    reason: Optional[str] = None  # e.g. "http_error", "timeout", "guardrail_rejected"


class TelemetryRecorder:
    def __init__(self, window_size: int = _WINDOW_SIZE, log_path: Path = _LOG_PATH):
        self._lock = threading.Lock()
        self._window_size = window_size
        self._windows: Dict[str, Deque[CallOutcome]] = {}
        self._log_path = log_path

    def record(self, outcome: CallOutcome) -> None:
        with self._lock:
            window = self._windows.setdefault(outcome.model_id, deque(maxlen=self._window_size))
            window.append(outcome)
        self._append_to_disk(outcome)

    def _append_to_disk(self, outcome: CallOutcome) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": time.time(),
                            "model_id": outcome.model_id,
                            "task": outcome.task,
                            "success": outcome.success,
                            "latency_ms": outcome.latency_ms,
                            "reason": outcome.reason,
                        }
                    )
                    + "\n"
                )
        except OSError:
            pass  # telemetry is best-effort; never fail the request over it

    def stats(self, model_id: str) -> dict:
        """Aggregate stats over the rolling window. None fields mean 'no data yet'."""
        with self._lock:
            window = list(self._windows.get(model_id, []))

        if not window:
            return {"sample_size": 0, "success_rate": None, "avg_latency_ms": None}

        successes = [o for o in window if o.success]
        latencies = [o.latency_ms for o in successes] or [o.latency_ms for o in window]

        return {
            "sample_size": len(window),
            "success_rate": len(successes) / len(window),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        }


default_telemetry = TelemetryRecorder()
