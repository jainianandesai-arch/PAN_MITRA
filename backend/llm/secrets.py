"""
Secret/env resolution shared by the whole llm package.

Mirrors the exact lookup rules already used in backend/mas_engine.py
(Streamlit secrets first, then environment variables, ignoring obvious
placeholder values), but has no hard dependency on Streamlit so the
package can be imported and unit-tested outside a Streamlit process.
"""

import os

_PLACEHOLDER_PREFIXES = ("YOUR_", "CHANGE_ME", "REPLACE_")
_PLACEHOLDER_EXACT = {"TODO"}


def get_secret(name: str, default: str = "") -> str:
    value = None
    try:
        import streamlit as st  # imported lazily; optional dependency for this package

        value = st.secrets.get(name, None)
    except Exception:
        value = None

    if value:
        return str(value).strip()

    return os.getenv(name, default).strip()


def get_configured_secret(*names: str) -> str:
    """Return the first configured (non-empty, non-placeholder) secret among `names`."""
    for name in names:
        value = get_secret(name)
        upper = value.upper()
        if value and not upper.startswith(_PLACEHOLDER_PREFIXES) and upper not in _PLACEHOLDER_EXACT:
            return value
    return ""


def get_setting_float(name: str, default: float) -> float:
    try:
        return float(get_secret(name, str(default)))
    except ValueError:
        return default
