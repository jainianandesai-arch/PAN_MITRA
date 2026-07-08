"""
Canonical PII / DPDP-sensitive-data patterns.

Shared by every module that needs to detect or redact personal data before
it reaches a cloud LLM (mas_engine.py) or gets written to the human-review
queue (hitl.py).

Before this module existed, these regex patterns were maintained
independently in two places and had already drifted apart:
  - mas_engine.py had 7 labeled patterns (AADHAAR/PAN/EMAIL/PHONE/IFSC/
    ACCOUNT/DOB), used for type-specific redaction before an LLM call.
  - hitl.py had 6 unlabeled patterns — the same six, minus DOB — used for
    uniform redaction before writing a review record to SQLite.
That means date-of-birth text was being redacted before LLM calls but
NOT before being written to the human-review queue. Consolidating onto
one list fixes that gap as a side effect. See CLEANUP_NOTES.md, "Session 3".
"""

import re


PII_PATTERNS = (
    ("AADHAAR", re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)),
    ("EMAIL", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
    ("PHONE", re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")),
    ("IFSC", re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.IGNORECASE)),
    ("ACCOUNT", re.compile(r"\b(?:account|a/c|acct)[\s:.-]*(?:no\.?|number)?[\s:.-]*\d{9,18}\b", re.IGNORECASE)),
    ("DOB", re.compile(r"\b(?:dob|date of birth)[\s:.-]*\d{1,2}[\s/-]\d{1,2}[\s/-]\d{2,4}\b", re.IGNORECASE)),
)


def has_personal_data(text):

    return any(pattern.search(text or "") for _, pattern in PII_PATTERNS)


def redact_personal_data(text, labeled=True):
    """
    Redact all recognized PII in `text`.

    labeled=True  -> type-specific placeholders, e.g. "[REDACTED_AADHAAR]".
                      Used before sending text to a cloud LLM: knowing that
                      *an account number was present* (without seeing it)
                      helps the model still reason about the question.
    labeled=False -> a single generic "[REDACTED_PERSONAL_DATA]" placeholder.
                      Used for the HITL review queue, where a human reviewer
                      only needs to know something was masked, not its type.
    """

    redacted = text or ""
    for label, pattern in PII_PATTERNS:
        placeholder = f"[REDACTED_{label}]" if labeled else "[REDACTED_PERSONAL_DATA]"
        redacted = pattern.sub(placeholder, redacted)

    return redacted
