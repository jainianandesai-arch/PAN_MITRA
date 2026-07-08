"""
Optional "preferred provider" override, set from the Settings UI.

Without this, the router always picks among candidates via the
priority/health/telemetry/cost scoring in scoring.py -- reasonable, but
opaque: if every candidate happens to be misconfigured, there is no way for
an operator to say "use *this* one, I know it works" short of editing
models.yaml/routing.yaml.

Two layers:
  - in-memory (`_current`), process-wide, applies immediately for the rest
    of this run -- like health.py's HealthMonitor, this is shared
    infrastructure state, not a per-request concern.
  - persisted (`data/user_override.json`, gitignored), loaded once at import
    time so a saved preference survives a restart. Contains a plaintext API
    key, same risk profile as .env -- keep it out of version control.
"""

from __future__ import annotations

import json
import os
from typing import Optional

_OVERRIDE_PATH = os.path.join(os.path.dirname(__file__), "data", "user_override.json")


def _load_from_disk() -> dict:
    try:
        with open(_OVERRIDE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


_current: dict = _load_from_disk()


def get_override() -> dict:
    """Returns {} if no provider is currently preferred, else {"model_id", "api_key"}."""
    return dict(_current)


def has_persisted_override() -> bool:
    return os.path.exists(_OVERRIDE_PATH)


def set_override(model_id: str, api_key: Optional[str] = None, persist: bool = False) -> None:
    global _current
    _current = {"model_id": model_id, "api_key": api_key}
    if persist:
        _persist(_current)
    elif has_persisted_override():
        _remove_persisted()


def clear_override(persist: bool = False) -> None:
    global _current
    _current = {}
    if persist:
        _remove_persisted()


def _persist(data: dict) -> None:
    directory = os.path.dirname(_OVERRIDE_PATH)
    os.makedirs(directory, exist_ok=True)
    with open(_OVERRIDE_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def _remove_persisted() -> None:
    try:
        os.remove(_OVERRIDE_PATH)
    except FileNotFoundError:
        pass
