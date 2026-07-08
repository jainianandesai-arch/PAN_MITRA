import os
import sqlite3
from datetime import datetime

from .env_config import get_secret as _secret
from .pii_patterns import redact_personal_data as _redact_pii

# Single unified table for the whole PAN request lifecycle -- every outcome
# (guidance given, escalated, blocked, submitted, completed) writes to the
# same row, the same way, instead of splitting escalations off into a
# separate database (backend/hitl.py, now unused by the live PAN flow).
# That split was the direct cause of a real bug: "escalated" was a defined
# status here that nothing ever set, because escalation only ever wrote to
# the other table -- escalated requests were invisible to Tracked
# Requests/Analytics. One table, written by one code path, can't drift like
# that.
STATUSES = ("guidance_provided", "escalated", "submitted_by_vle", "completed", "blocked")
SERVICE_TYPES = ("new_pan", "pan_correction", "pan_reprint", "instant_epan")


def _db_path():

    configured = _secret("PAN_TRACKING_DB_PATH", "")
    if configured:
        return configured

    return os.path.join(os.path.dirname(__file__), "pan_applications.sqlite3")


def _redact(text):

    return _redact_pii(text or "", labeled=False)


def _now():

    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _connect():

    path = _db_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pan_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            service_type TEXT NOT NULL,
            applicant_label TEXT NOT NULL,
            query TEXT,
            guidance_shown TEXT,
            status TEXT NOT NULL DEFAULT 'guidance_provided',
            confidence REAL NOT NULL,
            escalation_reason TEXT,
            notes TEXT,
            resolved_at TEXT
        )
        """
    )
    return conn


def create_application(service_type, applicant_label, guidance_shown="", confidence=0.0, notes="", query="", status="guidance_provided"):

    if status not in STATUSES:
        status = "guidance_provided"

    try:
        with _connect() as conn:
            timestamp = _now()
            cursor = conn.execute(
                """
                INSERT INTO pan_applications (
                    created_at, updated_at, service_type, applicant_label,
                    query, guidance_shown, status, confidence, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    timestamp,
                    service_type or "new_pan",
                    _redact(applicant_label)[:200],
                    _redact(query)[:4000],
                    _redact(guidance_shown)[:12000],
                    status,
                    float(confidence or 0.0),
                    _redact(notes)[:2000],
                ),
            )
            return cursor.lastrowid
    except Exception:
        return None


def update_status(app_id, status, notes=""):

    if status not in STATUSES:
        return False

    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE pan_applications
                SET status = ?, updated_at = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
                WHERE id = ?
                """,
                (status, _now(), notes, _redact(notes)[:2000], int(app_id)),
            )
            return True
    except Exception:
        return False


def escalate(app_id, service_type, applicant_label, query, confidence, reason):
    """Create-or-update a single row as escalated -- the one place any
    escalation (deterministic low-confidence gate or the agent's own
    escalate_to_officer tool) goes through, so it's never possible for an
    escalation to exist without showing up in Tracked Requests/Analytics."""

    reason = reason or "Needs human review"

    if app_id:
        try:
            with _connect() as conn:
                conn.execute(
                    """
                    UPDATE pan_applications
                    SET status = 'escalated', updated_at = ?, escalation_reason = ?
                    WHERE id = ?
                    """,
                    (_now(), _redact(reason)[:2000], int(app_id)),
                )
                return int(app_id)
        except Exception:
            return None

    try:
        with _connect() as conn:
            timestamp = _now()
            cursor = conn.execute(
                """
                INSERT INTO pan_applications (
                    created_at, updated_at, service_type, applicant_label,
                    query, status, confidence, escalation_reason
                )
                VALUES (?, ?, ?, ?, ?, 'escalated', ?, ?)
                """,
                (
                    timestamp,
                    timestamp,
                    service_type or "new_pan",
                    _redact(applicant_label)[:200],
                    _redact(query)[:4000],
                    float(confidence or 0.0),
                    _redact(reason)[:2000],
                ),
            )
            return cursor.lastrowid
    except Exception:
        return None


def resolve_escalation(app_id, operator_note="Reviewed"):

    try:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE pan_applications
                SET resolved_at = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (_now(), _redact(operator_note or "Reviewed")[:2000], _now(), int(app_id)),
            )
            return True
    except Exception:
        return False


def list_pending_escalations(limit=50):

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM pan_applications
                WHERE status = 'escalated' AND resolved_at IS NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def get_application(app_id):

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM pan_applications WHERE id = ?",
                (int(app_id),),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


def list_applications(status=None, service_type=None, limit=50):

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM pan_applications WHERE 1=1"
            params = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if service_type:
                query += " AND service_type = ?"
                params.append(service_type)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def stats():

    try:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            by_service = conn.execute(
                "SELECT service_type, COUNT(*) AS count FROM pan_applications GROUP BY service_type"
            ).fetchall()
            by_status = conn.execute(
                "SELECT status, COUNT(*) AS count FROM pan_applications GROUP BY status"
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) AS count FROM pan_applications").fetchone()
            return {
                "total": total["count"] if total else 0,
                "by_service_type": {row["service_type"]: row["count"] for row in by_service},
                "by_status": {row["status"]: row["count"] for row in by_status},
            }
    except Exception:
        return {"total": 0, "by_service_type": {}, "by_status": {}}
