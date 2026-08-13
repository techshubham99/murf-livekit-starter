"""
Day 8 - Call Analytics Module for ShikshaMitra AI

Manages call session records, exercise completion tracking,
and call performance analytics in SQLite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .database import get_db_connection

logger = logging.getLogger("agent.call_analytics")


# ============================================================
# TABLE INITIALIZATION
# ============================================================


def initialize_call_analytics_table() -> None:
    """Create the call_analytics table if it does not exist."""
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS call_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id TEXT UNIQUE NOT NULL,
                learner_id TEXT,
                channel TEXT DEFAULT 'browser',
                started_at TEXT NOT NULL,
                ended_at TEXT,
                duration_seconds INTEGER DEFAULT 0,
                exercise_completed INTEGER DEFAULT 0,
                outcome TEXT DEFAULT 'IN_PROGRESS',
                created_at TEXT NOT NULL
            )
            """
        )
        # Older databases created before IN_PROGRESS existed marked active calls
        # as failed.  Only unfinished rows are migrated; completed outcomes stay
        # untouched.
        conn.execute(
            """
            UPDATE call_analytics
            SET outcome = 'IN_PROGRESS'
            WHERE ended_at IS NULL AND outcome = 'FAILED'
            """
        )
        conn.commit()
    logger.info("call_analytics table initialized")


# ============================================================
# CALL RECORD LIFECYCLE
# ============================================================


def start_call_record(
    call_id: str,
    learner_id: str | None = None,
    channel: str = "browser",
) -> dict[str, Any]:
    """
    Insert a new call record when a real voice call starts.
    Uses INSERT OR IGNORE to prevent duplicate records for the same call_id.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO call_analytics (
                    call_id, learner_id, channel, started_at, outcome, created_at
                ) VALUES (?, ?, ?, ?, 'IN_PROGRESS', ?)
                """,
                (call_id, learner_id or "anonymous", channel, now_iso, now_iso),
            )
            conn.commit()
        logger.info(
            "[CALL ANALYTICS] Call started: call_id=%s, learner_id=%s, channel=%s",
            call_id,
            learner_id,
            channel,
        )
        return {"success": True, "call_id": call_id}
    except Exception as exc:
        logger.exception("[CALL ANALYTICS] Failed to start call record: %s", exc)
        return {"success": False, "error": str(exc)}


def mark_exercise_completed(call_id: str) -> dict[str, Any]:
    """
    Mark exercise as completed (1) for the given call_id.
    Called when score_spoken_answer evaluates a correct answer.
    """
    try:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE call_analytics
                SET exercise_completed = 1
                WHERE call_id = ?
                """,
                (call_id,),
            )
            conn.commit()
        logger.info(
            "[CALL ANALYTICS] Exercise completed for call_id=%s -> SUCCESS", call_id
        )
        return {"success": True, "call_id": call_id}
    except Exception as exc:
        logger.exception("[CALL ANALYTICS] Failed to mark exercise completed: %s", exc)
        return {"success": False, "error": str(exc)}


def end_call_record(call_id: str) -> dict[str, Any]:
    """
    Finalize a call record when the session ends.
    Computes duration and sets outcome (SUCCESS if exercise_completed=1 else FAILED).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT started_at, exercise_completed FROM call_analytics WHERE call_id = ?",
                (call_id,),
            ).fetchone()

            if not row:
                logger.warning(
                    "[CALL ANALYTICS] Call record not found for end: call_id=%s",
                    call_id,
                )
                return {"success": False, "error": "Record not found"}

            started_at_str = row["started_at"]
            exercise_completed = row["exercise_completed"]
            outcome = "SUCCESS" if exercise_completed else "FAILED"

            duration_seconds = 0
            try:
                started_at = datetime.fromisoformat(started_at_str)
                ended_at = datetime.fromisoformat(now_iso)
                duration_seconds = int((ended_at - started_at).total_seconds())
            except Exception:
                pass

            conn.execute(
                """
                UPDATE call_analytics
                SET ended_at = ?, duration_seconds = ?, outcome = ?
                WHERE call_id = ?
                """,
                (now_iso, duration_seconds, outcome, call_id),
            )
            conn.commit()

        logger.info(
            "[CALL ANALYTICS] Call ended: call_id=%s, duration=%ds, outcome=%s",
            call_id,
            duration_seconds,
            outcome,
        )
        return {
            "success": True,
            "call_id": call_id,
            "duration": duration_seconds,
            "outcome": outcome,
        }
    except Exception as exc:
        logger.exception("[CALL ANALYTICS] Failed to end call record: %s", exc)
        return {"success": False, "error": str(exc)}


# ============================================================
# SUMMARY & LISTING
# ============================================================


def get_analytics_summary() -> dict[str, Any]:
    """Calculate and return aggregate analytics metrics from SQLite."""
    with get_db_connection() as conn:
        row_total = conn.execute(
            "SELECT COUNT(*) as count FROM call_analytics"
        ).fetchone()
        row_success = conn.execute(
            "SELECT COUNT(*) as count FROM call_analytics WHERE outcome = 'SUCCESS'"
        ).fetchone()
        row_failed = conn.execute(
            """
            SELECT COUNT(*) as count
            FROM call_analytics
            WHERE ended_at IS NOT NULL AND outcome = 'FAILED'
            """
        ).fetchone()

        total_calls = row_total["count"] if row_total else 0
        successful_calls = row_success["count"] if row_success else 0
        failed_calls = row_failed["count"] if row_failed else 0

        success_rate = (
            round((successful_calls / total_calls) * 100, 1) if total_calls > 0 else 0
        )

        return {
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": success_rate,
        }


def get_recent_calls(limit: int = 20) -> list[dict[str, Any]]:
    """Fetch recent calls for dashboard display."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT call_id, learner_id, channel, started_at, ended_at, duration_seconds, exercise_completed, outcome
            FROM call_analytics
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {
                "call_id": r["call_id"],
                "learner_id": r["learner_id"],
                "channel": r["channel"],
                "started_at": r["started_at"],
                "ended_at": r["ended_at"],
                "duration_seconds": r["duration_seconds"],
                "exercise_completed": bool(r["exercise_completed"]),
                "outcome": r["outcome"],
            }
            for r in rows
        ]
