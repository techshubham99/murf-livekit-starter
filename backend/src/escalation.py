"""
Day 7 – Escalation Module for ShikshaMitra AI

Persistent escalation requests for human teacher help.

Uses the existing SQLite database via database.get_db_connection().
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

from .database import get_db_connection

logger = logging.getLogger("agent.escalation")


# ============================================================
# SENSITIVE PATTERNS
# ============================================================

_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # card numbers
    re.compile(r"\b\d{10,12}\b"),  # bank account / long numbers
    re.compile(r"\b\d{4,6}\b(?=.*(?:otp|pin|code))", re.IGNORECASE),  # OTP/PIN
    re.compile(
        r"(?:password|passwd|api[_\s]?key|secret|token)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
]


def _sanitize_text(text: str) -> str:
    """Remove sensitive patterns from text."""
    if not text:
        return text
    sanitized = text
    for pattern in _SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized.strip()


# ============================================================
# TABLE INITIALIZATION
# ============================================================


def initialize_escalation_table() -> None:
    """Create the escalations table if it does not exist."""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_id TEXT UNIQUE NOT NULL,
                learner_id TEXT,
                learner_name TEXT,
                reason TEXT,
                summary TEXT,
                already_checked TEXT,
                urgency TEXT DEFAULT 'MEDIUM',
                language TEXT DEFAULT 'English',
                preferred_follow_up TEXT DEFAULT 'voice',
                status TEXT DEFAULT 'OPEN',
                created_at TEXT
            )
            """
        )
        try:
            conn.execute("ALTER TABLE escalations ADD COLUMN learner_name TEXT")
        except Exception:
            pass
        conn.commit()
    logger.info("[ESCALATION] Escalation table initialized")


# ============================================================
# REFERENCE ID GENERATION
# ============================================================


def generate_reference_id() -> str:
    """Generate a unique human-readable reference ID: ESC-XXXXXX."""
    import secrets

    hex_part = secrets.token_hex(3).upper()  # 6 hex chars
    ref_id = f"ESC-{hex_part}"

    # Ensure uniqueness
    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM escalations WHERE reference_id = ?",
            (ref_id,),
        ).fetchone()

    if existing:
        return generate_reference_id()

    return ref_id


# ============================================================
# DUPLICATE DETECTION
# ============================================================


def find_duplicate_escalation(
    learner_id: str,
    reason: str,
) -> dict[str, Any] | None:
    """Check if the learner already has an OPEN escalation for the same reason."""
    if not learner_id or not reason:
        return None

    with get_db_connection() as conn:
        row = conn.execute(
            """
            SELECT reference_id, reason, summary, status, created_at
            FROM escalations
            WHERE learner_id = ?
              AND reason = ?
              AND status = 'OPEN'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (learner_id, reason),
        ).fetchone()

    if row:
        return {
            "reference_id": row["reference_id"],
            "reason": row["reason"],
            "summary": row["summary"],
            "status": row["status"],
            "created_at": row["created_at"],
        }

    return None


# ============================================================
# CREATE ESCALATION
# ============================================================

VALID_URGENCIES = {"LOW", "MEDIUM", "HIGH"}
VALID_FOLLOW_UPS = {"voice", "text", "dashboard"}


def create_escalation_record(
    learner_id: str,
    reason: str,
    summary: str,
    already_checked: str = "",
    urgency: str = "MEDIUM",
    language: str = "English",
    preferred_follow_up: str = "voice",
    learner_name: str | None = None,
) -> dict[str, Any]:
    """
    Create a new escalation request.

    Returns:
        {
            "success": True,
            "reference_id": "ESC-XXXXXX",
            "status": "OPEN",
        }
    """

    # Validate urgency
    urgency = urgency.upper() if urgency else "MEDIUM"
    if urgency not in VALID_URGENCIES:
        urgency = "MEDIUM"

    # Validate follow-up
    preferred_follow_up = (preferred_follow_up or "voice").lower()
    if preferred_follow_up not in VALID_FOLLOW_UPS:
        preferred_follow_up = "voice"

    # Sanitize text fields
    sanitized_summary = _sanitize_text(summary or "")
    sanitized_checked = _sanitize_text(already_checked or "")
    sanitized_reason = _sanitize_text(reason or "Teacher Help")

    if not sanitized_summary:
        sanitized_summary = "Learner requested teacher help."

    # Try looking up learner name from memory if not provided
    if not learner_name and learner_id:
        try:
            from .memory import lookup_user_memory
            mem = lookup_user_memory(learner_id)
            if isinstance(mem, dict) and mem.get("name"):
                learner_name = mem.get("name")
        except Exception:
            pass

    # Check for duplicates
    duplicate = find_duplicate_escalation(learner_id, sanitized_reason)
    if duplicate:
        logger.info(
            "[ESCALATION] Duplicate found for learner=%s, returning existing %s",
            learner_id,
            duplicate["reference_id"],
        )
        return {
            "success": True,
            "reference_id": duplicate["reference_id"],
            "status": duplicate["status"],
            "duplicate": True,
        }

    # Generate reference ID
    reference_id = generate_reference_id()
    created_at = datetime.now(UTC).isoformat()

    logger.info("[ESCALATION] Creating request %s", reference_id)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO escalations (
                reference_id, learner_id, learner_name, reason, summary,
                already_checked, urgency, language,
                preferred_follow_up, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?)
            """,
            (
                reference_id,
                learner_id or "unknown",
                learner_name,
                sanitized_reason,
                sanitized_summary,
                sanitized_checked,
                urgency,
                language or "English",
                preferred_follow_up,
                created_at,
            ),
        )
        conn.commit()

    logger.info("[ESCALATION] Created %s", reference_id)
    logger.info("[ESCALATION] Status: OPEN")
    logger.info("[ESCALATION] Dashboard persistence successful")

    return {
        "success": True,
        "reference_id": reference_id,
        "status": "OPEN",
    }


# ============================================================
# GET ALL ESCALATIONS
# ============================================================


def get_all_escalations() -> list[dict[str, Any]]:
    """Return all escalation records ordered by newest first."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.reference_id, e.learner_id, e.learner_name,
                   e.reason, e.summary, e.already_checked, e.urgency,
                   e.language, e.preferred_follow_up, e.status, e.created_at,
                   l.name AS db_learner_name
            FROM escalations e
            LEFT JOIN learners l ON e.learner_id = l.user_id
            ORDER BY e.created_at DESC
            """
        ).fetchall()

    result = []
    for row in rows:
        name = row["learner_name"] or row["db_learner_name"] or row["learner_id"] or "Learner"
        result.append({
            "id": row["id"],
            "reference_id": row["reference_id"],
            "learner_id": row["learner_id"],
            "learner_name": name,
            "reason": row["reason"],
            "summary": row["summary"],
            "already_checked": row["already_checked"],
            "urgency": row["urgency"],
            "language": row["language"],
            "preferred_follow_up": row["preferred_follow_up"],
            "status": row["status"],
            "created_at": row["created_at"],
        })
    return result


# ============================================================
# UPDATE STATUS
# ============================================================

VALID_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED"}


def update_escalation_status(
    reference_id: str,
    new_status: str,
) -> dict[str, Any]:
    """Update the status of an escalation request."""

    new_status = (new_status or "").upper()
    if new_status not in VALID_STATUSES:
        return {
            "success": False,
            "error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}",
        }

    with get_db_connection() as conn:
        cursor = conn.execute(
            "UPDATE escalations SET status = ? WHERE reference_id = ?",
            (new_status, reference_id),
        )
        conn.commit()

    if cursor.rowcount == 0:
        return {
            "success": False,
            "error": f"Escalation {reference_id} not found.",
        }

    logger.info(
        "[ESCALATION] Updated %s → %s",
        reference_id,
        new_status,
    )

    return {
        "success": True,
        "reference_id": reference_id,
        "status": new_status,
    }
