"""
Backend Package
Core business logic for CSC Mitra AI

This package intentionally has NO submodule imports here. Previously it
unconditionally imported an `agents/` package that has since been removed
(see ../CLEANUP_NOTES.md) — that import ran every time ANY `backend.X`
submodule was imported (Python always executes a package's __init__.py
first), and was only not fatal because streamlit_app.py wraps its backend
imports in try/except ImportError and logs+degrades instead of crashing.

Keep this file free of eager imports. Submodules (mas_engine, database,
knowledge, llm, ...) are imported directly by whatever needs them.
"""

