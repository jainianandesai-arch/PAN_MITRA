"""
Shared environment/secrets access for the CSC Mitra backend.

Every backend module needs to read the same kind of configuration value
(API keys, feature flags, numeric thresholds) from either Streamlit's
`st.secrets` (when deployed on Streamlit Cloud) or process environment
variables / `.env` (when run locally with python-dotenv).

Before this module existed, the ~10-line "check st.secrets, fall back to
os.getenv" lookup was copy-pasted independently into database.py,
guardrails.py, hitl.py, mas_engine.py, and voice_assistant.py (the
placeholder-aware `configured_secret` variant was duplicated in both
mas_engine.py and voice_assistant.py too). This module is now the single
implementation; every other module imports from here instead of
redefining it. See CLEANUP_NOTES.md, "Session 3" for the audit that found
this and why it was consolidated here rather than left as-is or moved
onto `guardrails.py` (which had organically become the de facto shared
location for `setting()`, even though secrets access isn't really a
guardrail concern). voice_assistant.py itself was removed in Session 4's
rebrand — this history is kept for context on why the module looks the
way it does.

`guardrails.setting()` is kept as a thin, backward-compatible wrapper
around `get_secret()` here, since other modules already import it by
that name.
"""

import os

import streamlit as st
from dotenv import load_dotenv

# Every backend module eventually imports this one, so loading .env here
# (once, at import time) guarantees it's picked up regardless of which
# Streamlit entry script actually ran first (streamlit_app.py vs. a
# standalone pages/*.py) -- nothing in the codebase called load_dotenv()
# before this, so os.getenv() never saw .env locally at all.
load_dotenv()


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}


def get_secret(name, default=""):
    """Look up `name` in Streamlit secrets first, then the environment."""

    try:
        value = st.secrets.get(name, None)
    except Exception:
        value = None

    if value:
        return str(value).strip()

    return os.getenv(name, default).strip()


def get_configured_secret(*names):
    """
    Return the first of `names` that resolves to a real, non-placeholder
    value. Skips template placeholders such as "YOUR_API_KEY", "CHANGE_ME",
    "REPLACE_ME", or "TODO" left over from an unfilled .env/secrets.toml.
    """

    for name in names:
        value = get_secret(name)
        placeholder = value.upper()
        if (
            value
            and not placeholder.startswith("YOUR_")
            and not placeholder.startswith("CHANGE_ME")
            and not placeholder.startswith("REPLACE_")
            and placeholder != "TODO"
        ):
            return value

    return ""


def get_setting_int(name, default):

    try:
        return int(get_secret(name, str(default)))
    except ValueError:
        return default


def get_setting_float(name, default):

    try:
        return float(get_secret(name, str(default)))
    except ValueError:
        return default


def get_flag(name, default=False):

    value = get_secret(name, "true" if default else "false").lower()
    if value in TRUE_VALUES:
        return True
    if value in FALSE_VALUES:
        return False

    return default
