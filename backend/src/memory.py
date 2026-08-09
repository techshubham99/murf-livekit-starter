from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from .database import get_db_connection, initialize_database

logger = logging.getLogger("agent.memory")


def lookup_user_memory(user_id: str) -> dict[str, Any] | str:
    try:
        initialize_database()
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT user_id, name, language_preference, facts, last_interaction FROM learners WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row is None:
                return "no memory found"

            facts = {}
            if row["facts"]:
                try:
                    facts = json.loads(row["facts"])
                except json.JSONDecodeError:
                    logger.warning("Failed to parse facts JSON for user_id=%s", user_id)

            return {
                "user_id": row["user_id"],
                "name": row["name"],
                "language_preference": row["language_preference"],
                "facts": facts,
                "last_interaction": row["last_interaction"],
            }
    except Exception as error:
        logger.exception("lookup_user_memory failed for user_id=%s", user_id)
        return "no memory found"


ALLOWED_FACT_KEYS = {"learning_level", "current_topic", "topics_covered"}


def _merge_facts(existing_facts: dict[str, Any], new_facts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    for key in ALLOWED_FACT_KEYS:
        if key == "topics_covered":
            existing_topics = existing_facts.get("topics_covered")
            new_topics = new_facts.get("topics_covered")
            if isinstance(existing_topics, list) or isinstance(new_topics, list):
                merged_topics: list[str] = []
                seen = set()
                if isinstance(existing_topics, list):
                    for topic in existing_topics:
                        if isinstance(topic, str) and topic not in seen:
                            merged_topics.append(topic)
                            seen.add(topic)
                if isinstance(new_topics, list):
                    for topic in new_topics:
                        if isinstance(topic, str) and topic not in seen:
                            merged_topics.append(topic)
                            seen.add(topic)
                if merged_topics:
                    merged["topics_covered"] = merged_topics
        else:
            if key in new_facts and new_facts[key] is not None:
                merged[key] = new_facts[key]
            elif isinstance(existing_facts.get(key), str):
                merged[key] = existing_facts[key]

    return merged


def save_user_memory(
    user_id: str,
    name: str | None,
    language_preference: str | None,
    facts: dict[str, Any],
) -> str:
    try:
        initialize_database()
        existing = lookup_user_memory(user_id)
        existing_facts: dict[str, Any] = {}
        existing_name: str | None = None
        existing_language: str | None = None

        if isinstance(existing, dict):
            existing_facts = existing.get("facts", {}) or {}
            existing_name = existing.get("name")
            existing_language = existing.get("language_preference")

        sanitized_facts = {k: v for k, v in facts.items() if k in ALLOWED_FACT_KEYS}
        merged_facts = _merge_facts(existing_facts, sanitized_facts)
        merged_name = name or existing_name
        merged_language = language_preference or existing_language
        last_interaction = datetime.utcnow().isoformat()

        with get_db_connection() as conn:
            conn.execute(
                "REPLACE INTO learners (user_id, name, language_preference, facts, last_interaction) VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    merged_name,
                    merged_language,
                    json.dumps(merged_facts, ensure_ascii=False),
                    last_interaction,
                ),
            )
            conn.commit()

        return "memory saved"
    except Exception:
        logger.exception("save_user_memory failed for user_id=%s", user_id)
        return "memory save failed"
