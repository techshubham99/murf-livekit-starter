"""
Day 7 – Escalation Module Tests for ShikshaMitra AI

These tests validate the escalation database operations directly
without requiring LiveKit infrastructure.

Run with:
    cd backend
    uv run pytest tests/test_escalation.py -v
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from src.database import initialize_database
from src.escalation import (
    create_escalation_record,
    find_duplicate_escalation,
    generate_reference_id,
    get_all_escalations,
    initialize_escalation_table,
    update_escalation_status,
)


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture(autouse=True)
def _init_db():
    """Ensure database tables exist before each test."""
    initialize_database()
    initialize_escalation_table()


# ============================================================
# TABLE CREATION
# ============================================================


def test_escalation_table_creation():
    """Verify that the escalation table can be created without errors."""
    # Should not raise
    initialize_escalation_table()


# ============================================================
# REFERENCE ID FORMAT
# ============================================================


def test_reference_id_format():
    """Verify reference IDs follow ESC-XXXXXX format."""
    ref_id = generate_reference_id()
    assert ref_id.startswith("ESC-"), f"Expected ESC- prefix, got {ref_id}"
    assert len(ref_id) == 10, f"Expected 10 chars, got {len(ref_id)}: {ref_id}"
    assert re.match(
        r"^ESC-[0-9A-F]{6}$", ref_id
    ), f"Invalid format: {ref_id}"


def test_reference_ids_unique():
    """Verify multiple reference IDs are unique."""
    ids = {generate_reference_id() for _ in range(20)}
    assert len(ids) == 20, "Reference IDs should be unique"


# ============================================================
# CREATE ESCALATION
# ============================================================


def test_create_escalation():
    """Verify escalation record is created and returned correctly."""
    result = create_escalation_record(
        learner_id="test-learner-day7-create",
        reason="Teacher Help",
        summary="Student is struggling with recursion",
        already_checked="Explained recursion with a simple example",
        urgency="MEDIUM",
        language="English",
        preferred_follow_up="voice",
    )

    assert result["success"] is True
    assert result["status"] == "OPEN"
    assert result["reference_id"].startswith("ESC-")


def test_create_escalation_hindi():
    """Verify escalation with Hindi content works."""
    result = create_escalation_record(
        learner_id="test-hindi-learner",
        reason="Frustrated Learner",
        summary="विद्यार्थी recursion को समझने में कठिनाई महसूस कर रहा है।",
        already_checked="ShikshaMitra ने recursion को एक सरल उदाहरण से समझाने की कोशिश की।",
        urgency="MEDIUM",
        language="Hindi",
        preferred_follow_up="voice",
    )

    assert result["success"] is True
    assert result["status"] == "OPEN"


def test_create_escalation_defaults():
    """Verify default values are applied when optional fields are missing."""
    result = create_escalation_record(
        learner_id="test-defaults-learner",
        reason="Teacher Help",
        summary="Needs help",
    )

    assert result["success"] is True
    assert result["status"] == "OPEN"

    # Verify record in database
    escalations = get_all_escalations()
    found = [
        e
        for e in escalations
        if e["reference_id"] == result["reference_id"]
    ]
    assert len(found) == 1
    assert found[0]["urgency"] == "MEDIUM"
    assert found[0]["language"] == "English"
    assert found[0]["preferred_follow_up"] == "voice"


# ============================================================
# DUPLICATE PROTECTION
# ============================================================


def test_duplicate_protection():
    """Verify duplicate OPEN requests for same learner/reason are detected."""
    learner_id = "test-dup-learner-v2"
    reason = "Frustrated Learner"

    # Create first escalation
    result1 = create_escalation_record(
        learner_id=learner_id,
        reason=reason,
        summary="Learner is frustrated with loops",
        urgency="HIGH",
        language="Hindi",
    )

    assert result1["success"] is True
    ref1 = result1["reference_id"]

    # Create duplicate — should return existing
    result2 = create_escalation_record(
        learner_id=learner_id,
        reason=reason,
        summary="Still frustrated with loops",
        urgency="HIGH",
        language="Hindi",
    )

    assert result2["success"] is True
    assert result2["reference_id"] == ref1
    assert result2.get("duplicate") is True


def test_different_reasons_not_duplicate():
    """Verify different reasons create separate escalations."""
    learner_id = "test-diff-reason-learner"

    result1 = create_escalation_record(
        learner_id=learner_id,
        reason="Teacher Help",
        summary="Needs teacher for recursion",
    )

    result2 = create_escalation_record(
        learner_id=learner_id,
        reason="Frustrated Learner",
        summary="Frustrated with loops",
    )

    assert result1["reference_id"] != result2["reference_id"]


# ============================================================
# STATUS UPDATES
# ============================================================


def test_update_escalation_status():
    """Verify status can be updated from OPEN → IN_PROGRESS → RESOLVED."""
    result = create_escalation_record(
        learner_id="test-status-learner-v2",
        reason="Teacher Help",
        summary="Needs help with Python",
        urgency="LOW",
        language="English",
    )

    ref_id = result["reference_id"]

    # Update to IN_PROGRESS
    update1 = update_escalation_status(ref_id, "IN_PROGRESS")
    assert update1["success"] is True
    assert update1["status"] == "IN_PROGRESS"

    # Update to RESOLVED
    update2 = update_escalation_status(ref_id, "RESOLVED")
    assert update2["success"] is True
    assert update2["status"] == "RESOLVED"


def test_invalid_status_rejected():
    """Verify invalid status values are rejected."""
    result = update_escalation_status("ESC-FAKE00", "INVALID_STATUS")
    assert result["success"] is False


def test_update_nonexistent_escalation():
    """Verify updating a nonexistent reference ID fails gracefully."""
    result = update_escalation_status("ESC-000000", "RESOLVED")
    assert result["success"] is False


# ============================================================
# LIST ESCALATIONS
# ============================================================


def test_get_all_escalations():
    """Verify escalations can be listed."""
    escalations = get_all_escalations()
    assert isinstance(escalations, list)


# ============================================================
# SENSITIVE DATA
# ============================================================


def test_sensitive_data_sanitized():
    """Verify sensitive patterns are removed from summaries."""
    result = create_escalation_record(
        learner_id="test-sensitive-learner-v2",
        reason="Teacher Help",
        summary="My password is: secret123 and card 1234-5678-9012-3456",
        urgency="LOW",
        language="English",
    )

    assert result["success"] is True

    # The card number should be redacted
    escalations = get_all_escalations()
    for esc in escalations:
        if esc["reference_id"] == result["reference_id"]:
            assert "1234-5678-9012-3456" not in esc["summary"]
            break


def test_urgency_normalization():
    """Verify invalid urgency is normalized to MEDIUM."""
    result = create_escalation_record(
        learner_id="test-urgency-learner",
        reason="Teacher Help",
        summary="Test urgency",
        urgency="INVALID",
    )

    assert result["success"] is True

    escalations = get_all_escalations()
    for esc in escalations:
        if esc["reference_id"] == result["reference_id"]:
            assert esc["urgency"] == "MEDIUM"
            break
