"""
Loads the YAML model catalog and routing table, and resolves each model
definition against currently-configured secrets/env vars. This is the
"configuration-driven" layer: adding, removing, or reordering models never
requires touching Python code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from .secrets import get_configured_secret, get_secret, get_setting_float
from .user_override import get_override

_CONFIG_DIR = Path(__file__).parent / "config"


@dataclass
class ModelSpec:
    """A resolved, ready-to-call model — or one that's unavailable (no key configured)."""

    id: str
    provider: str
    base_url: str
    model: str
    api_key: str
    timeout: float
    context_length: int
    free: bool
    tags: List[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return bool(self.api_key)


class ModelRegistry:
    def __init__(self, models_path: Optional[Path] = None, routing_path: Optional[Path] = None):
        self.models_path = models_path or (_CONFIG_DIR / "models.yaml")
        self.routing_path = routing_path or (_CONFIG_DIR / "routing.yaml")
        self._raw_models: Dict[str, dict] = {}
        self._routing: dict = {}
        self._load()

    def _load(self) -> None:
        with open(self.models_path, "r", encoding="utf-8") as fh:
            self._raw_models = (yaml.safe_load(fh) or {}).get("models", {})
        with open(self.routing_path, "r", encoding="utf-8") as fh:
            self._routing = yaml.safe_load(fh) or {}

    def reload(self) -> None:
        """Re-read the YAML files from disk (e.g. after editing the catalog live)."""
        self._load()

    def resolve(self, model_id: str) -> ModelSpec:
        raw = self._raw_models.get(model_id)
        if raw is None:
            raise KeyError(f"Unknown model id in registry: {model_id!r}")

        base_url = get_secret(raw["base_url_env"], raw.get("base_url_default", ""))
        model_name = get_secret(raw["model_env"], raw.get("model_default", ""))
        api_key = get_configured_secret(*raw["key_env"])
        override = get_override()
        if override.get("model_id") == model_id and override.get("api_key"):
            api_key = override["api_key"]
        timeout = get_setting_float(raw.get("timeout_env", ""), raw.get("timeout_default", 30.0))

        return ModelSpec(
            id=model_id,
            provider=raw.get("provider", "openai_compatible"),
            base_url=base_url,
            model=model_name,
            api_key=api_key,
            timeout=timeout,
            context_length=int(raw.get("context_length", 8000)),
            free=bool(raw.get("free", False)),
            tags=list(raw.get("tags", [])),
        )

    def all_model_ids(self) -> List[str]:
        return list(self._raw_models.keys())

    def display_name(self, model_id: str) -> str:
        raw = self._raw_models.get(model_id, {})
        return raw.get("display_name", model_id)

    def candidates_for_task(self, task: str, fast_mode: bool = False) -> List[str]:
        tasks = self._routing.get("tasks", {})
        entry = tasks.get(task)
        if entry is None:
            default_task = self._routing.get("default_task", "rag_answer")
            entry = tasks.get(default_task, {})

        if fast_mode and "fast_mode" in entry:
            return list(entry["fast_mode"])
        return list(entry.get("default", []))
