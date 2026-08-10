from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any


# ============================================================
# PATHS
# ============================================================

EXERCISES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "exercises.json"
)


# ============================================================
# STOPWORDS
# ============================================================

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "will",
    "with",
    "this",
    "that",
    "which",
    "their",
    "your",
    "you",
    "do",
    "does",
    "did",
    "so",
    "not",
    "can",
    "should",
    "may",
    "what",
    "how",
    "why",
    "where",
    "when",
    "who",
    "please",
    "tell",
    "me",
}


# ============================================================
# TOPIC ALIASES
# ============================================================

TOPIC_ALIASES = {
    "python": [
        "python",
        "programming",
        "coding",
        "code",
    ],
    "mathematics": [
        "math",
        "mathematics",
        "maths",
        "algebra",
        "geometry",
        "numbers",
        "calculation",
        "arithmetic",
    ],
    "english grammar": [
        "english grammar",
        "grammar",
        "sentence",
        "verbs",
        "nouns",
        "articles",
        "tenses",
    ],
    "vocabulary": [
        "vocabulary",
        "words",
        "synonym",
        "antonym",
        "word meaning",
    ],
    "computer science": [
        "computer science",
        "cs",
        "computer",
        "algorithm",
        "binary",
        "data structure",
        "data structures",
        "network",
        "networks",
        "cpu",
        "ram",
        "html",
        "database",
    ],
}


# ============================================================
# NUMBER WORDS
# ============================================================

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "seventy": "70",
    "eighty": "80",
    "ninety": "90",
}


# ============================================================
# SESSION SCORE STORAGE
# ============================================================
# In-memory only.
# This is for the current running agent/session.
# Day 4 persistent memory remains in SQLite separately.

_SESSION_SCORES: dict[str, dict[str, Any]] = {}


def start_score_session(session_id: str) -> dict[str, Any]:
    """
    Start or reset the score tracker for a learner/session.
    """

    _SESSION_SCORES[session_id] = {
        "attempted": 0,
        "correct": 0,
        "partial": 0,
        "incorrect": 0,
        "total_points": 0.0,
        "answers": [],
    }

    return _SESSION_SCORES[session_id]


def record_answer_result(
    session_id: str,
    score: float,
    correct: bool,
    question: str = "",
    learner_answer: str = "",
) -> dict[str, Any]:
    """
    Record one evaluated answer in the current session.
    """

    if session_id not in _SESSION_SCORES:
        start_score_session(session_id)

    session = _SESSION_SCORES[session_id]

    session["attempted"] += 1
    session["total_points"] += score

    if correct:
        session["correct"] += 1
    elif score > 0:
        session["partial"] += 1
    else:
        session["incorrect"] += 1

    session["answers"].append(
        {
            "question": question,
            "learner_answer": learner_answer,
            "score": score,
            "correct": correct,
        }
    )

    return session


def get_session_score(session_id: str) -> dict[str, Any]:
    """
    Return the current score for a learner/session.
    """

    session = _SESSION_SCORES.get(session_id)

    if not session:
        return {
            "success": False,
            "message": "No questions have been attempted yet.",
        }

    attempted = session["attempted"]
    total_points = session["total_points"]

    percentage = (
        round((total_points / attempted) * 100, 1)
        if attempted
        else 0
    )

    return {
        "success": True,
        "attempted": attempted,
        "correct": session["correct"],
        "partial": session["partial"],
        "incorrect": session["incorrect"],
        "total_points": round(total_points, 2),
        "percentage": percentage,
    }


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def _normalize(text: str | None) -> str:
    """
    Normalize text for comparison.
    """

    if not text:
        return ""

    text = text.lower().strip()

    # Convert common number words to digits.
    for word, number in NUMBER_WORDS.items():
        text = re.sub(
            rf"\b{re.escape(word)}\b",
            number,
            text,
        )

    # Remove punctuation.
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # Remove extra spaces.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _words(text: str) -> list[str]:
    """
    Return meaningful normalized words.
    """

    return [
        word
        for word in _normalize(text).split()
        if word and word not in STOPWORDS
    ]


# ============================================================
# TOPIC MATCHING
# ============================================================

def _matches_topic(
    exercise_topic: str,
    requested_topic: str,
) -> bool:
    """
    Check whether an exercise matches the requested topic.
    """

    normalized_ex = _normalize(exercise_topic)
    normalized_req = _normalize(requested_topic)

    if not normalized_req:
        return True

    if (
        normalized_req in normalized_ex
        or normalized_ex in normalized_req
    ):
        return True

    for alias_group, aliases in TOPIC_ALIASES.items():

        requested_matches = any(
            alias in normalized_req
            for alias in aliases
        )

        exercise_matches = any(
            alias in normalized_ex
            for alias in aliases
        )

        if requested_matches and exercise_matches:
            return True

    requested_tokens = set(_words(requested_topic))
    exercise_tokens = set(_words(exercise_topic))

    return bool(
        requested_tokens
        and exercise_tokens
        and requested_tokens.intersection(exercise_tokens)
    )


# ============================================================
# LEVEL NORMALIZATION
# ============================================================

def _normalize_level(level: str | None) -> str:
    """
    Normalize beginner/intermediate/advanced input.
    """

    if not level:
        return ""

    normalized = _normalize(level)

    if normalized.startswith("beg"):
        return "beginner"

    if normalized.startswith("int"):
        return "intermediate"

    if normalized.startswith("adv"):
        return "advanced"

    return normalized


# ============================================================
# LOAD EXERCISES
# ============================================================

def _load_exercise_data() -> list[dict[str, Any]]:
    """
    Load exercises from exercises.json.
    """

    if not EXERCISES_PATH.exists():
        raise FileNotFoundError(
            f"Exercise data file not found at {EXERCISES_PATH}"
        )

    with EXERCISES_PATH.open(
        "r",
        encoding="utf-8",
    ) as handle:

        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(
            "Exercise data must be a list of exercises."
        )

    valid_exercises = []

    for exercise in data:

        if not isinstance(exercise, dict):
            continue

        required_fields = {
            "id",
            "level",
            "topic",
            "question",
            "expected_answer",
        }

        if not required_fields.issubset(exercise.keys()):
            continue

        valid_exercises.append(exercise)

    if not valid_exercises:
        raise ValueError(
            "No valid exercises found in exercise dataset."
        )

    return valid_exercises


# ============================================================
# FIND NEXT EXERCISE
# ============================================================

def find_next_exercise(
    level: str | None,
    topic: str | None,
    exclude_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Find a suitable learning exercise.

    The exercise is selected using learner level and topic.
    """

    try:
        exercises = _load_exercise_data()

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ):

        return {
            "success": False,
            "error": "data_unavailable",
            "message": (
                "I'm unable to fetch a practice exercise right now. "
                "I can still explain the topic or help you practice "
                "another way."
            ),
        }

    normalized_level = _normalize_level(level)
    normalized_topic = _normalize(topic)

    exclude_ids = exclude_ids or []

    # First preference: level + topic.
    level_matches = [
        exercise
        for exercise in exercises
        if _normalize_level(
            exercise.get("level")
        ) == normalized_level
    ]

    topic_matches = [
        exercise
        for exercise in level_matches
        if _matches_topic(
            exercise.get("topic", ""),
            topic or "",
        )
    ]

    # Second preference: topic only.
    if not topic_matches and normalized_topic:

        topic_matches = [
            exercise
            for exercise in exercises
            if _matches_topic(
                exercise.get("topic", ""),
                topic or "",
            )
        ]

    # Third preference: level only.
    preferred = (
        topic_matches
        or level_matches
        or exercises
    )

    available = [
        exercise
        for exercise in preferred
        if exercise.get("id") not in exclude_ids
    ]

    if not available:

        return {
            "success": False,
            "error": "no_match",
            "message": (
                "I couldn't find a suitable exercise for "
                "that topic and level right now. "
                "Would you like to try another topic?"
            ),
        }

    exercise = random.choice(available)

    return {
        "success": True,
        "exercise": exercise,
    }


# ============================================================
# ANSWER NORMALIZATION HELPERS
# ============================================================

def _is_short_fact_answer(expected: str) -> bool:
    """
    Detect short factual answers such as:
    CPU = Central Processing Unit
    RAM = Random Access Memory
    HTML = HyperText Markup Language
    """

    words = _words(expected)

    return len(words) <= 5


def _contains_all_important_words(
    expected_words: set[str],
    answer_words: set[str],
) -> bool:

    if not expected_words:
        return False

    matched = expected_words.intersection(answer_words)

    ratio = len(matched) / len(expected_words)

    return ratio >= 0.75


# ============================================================
# EVALUATE SPOKEN ANSWER
# ============================================================

def evaluate_spoken_answer(
    question: str,
    expected_answer: str,
    learner_answer: str,
) -> tuple[float, bool, str]:
    """
    Evaluate a learner's spoken answer.

    Returns:

        score:
            1.0 = correct
            0.5 = partially correct
            0.0 = incorrect

        correct:
            True only for a fully correct answer

        feedback:
            Natural feedback for the learner.
    """

    if (
        not learner_answer
        or not expected_answer
    ):

        return (
            0.0,
            False,
            "I couldn't evaluate your answer right now, "
            "but we can try the question again.",
        )

    normalized_expected = _normalize(
        expected_answer
    )

    normalized_answer = _normalize(
        learner_answer
    )

    if not normalized_expected or not normalized_answer:

        return (
            0.0,
            False,
            "I couldn't evaluate your answer right now, "
            "but we can try the question again.",
        )

    # --------------------------------------------------------
    # Exact match
    # --------------------------------------------------------

    if normalized_expected == normalized_answer:

        return (
            1.0,
            True,
            f"Correct! {expected_answer}",
        )

    # --------------------------------------------------------
    # Expected phrase contained in learner answer
    # --------------------------------------------------------

    if normalized_expected in normalized_answer:

        return (
            1.0,
            True,
            f"Correct! {expected_answer}",
        )

    expected_words = set(
        _words(expected_answer)
    )

    answer_words = set(
        _words(learner_answer)
    )

    if not expected_words or not answer_words:

        return (
            0.0,
            False,
            f"Not quite. {expected_answer}",
        )

    common_words = (
        expected_words.intersection(answer_words)
    )

    similarity = (
        len(common_words)
        / max(1, len(expected_words))
    )

    # --------------------------------------------------------
    # Short factual answers
    #
    # Example:
    # Expected: Central Processing Unit
    # Answer:   Central Public School
    #
    # "central" is common, but the answer is still wrong.
    # Therefore short fact questions need stricter matching.
    # --------------------------------------------------------

    if _is_short_fact_answer(expected_answer):

        if _contains_all_important_words(
            expected_words,
            answer_words,
        ):

            return (
                1.0,
                True,
                f"Correct! {expected_answer}",
            )

        # For short factual answers, one common word
        # should NOT make the answer partially correct.
        if similarity < 0.75:

            return (
                0.0,
                False,
                f"Not quite. {expected_answer}",
            )

    # --------------------------------------------------------
    # Normal conceptual answers
    #
    # Example:
    # Expected:
    # "A variable is used to store a value."
    #
    # Learner:
    # "Variable stores a value."
    #
    # This should be accepted.
    # --------------------------------------------------------

    if similarity >= 0.70:

        return (
            1.0,
            True,
            f"Correct! {expected_answer}",
        )

    if similarity >= 0.35:

        return (
            0.5,
            False,
            f"Almost right. {expected_answer}",
        )

    return (
        0.0,
        False,
        f"Not quite. {expected_answer}",
    )


# ============================================================
# SCORE + RECORD ANSWER
# ============================================================

def score_and_record_answer(
    session_id: str,
    question: str,
    expected_answer: str,
    learner_answer: str,
) -> dict[str, Any]:
    """
    Evaluate an answer and automatically record it
    in the current session score.
    """

    score, correct, feedback = evaluate_spoken_answer(
        question=question,
        expected_answer=expected_answer,
        learner_answer=learner_answer,
    )

    session = record_answer_result(
        session_id=session_id,
        score=score,
        correct=correct,
        question=question,
        learner_answer=learner_answer,
    )

    return {
        "success": True,
        "score": score,
        "correct": correct,
        "feedback": feedback,
        "session": {
            "attempted": session["attempted"],
            "correct": session["correct"],
            "partial": session["partial"],
            "incorrect": session["incorrect"],
            "total_points": round(
                session["total_points"],
                2,
            ),
        },
    }


# ============================================================
# GET FINAL SESSION SCORE
# ============================================================

def format_session_score(
    session_id: str,
) -> dict[str, Any]:
    """
    Return a learner-friendly overall score.
    """

    result = get_session_score(session_id)

    if not result.get("success"):

        return {
            "success": False,
            "message": (
                "You haven't attempted any questions yet."
            ),
        }

    attempted = result["attempted"]
    correct = result["correct"]
    partial = result["partial"]
    incorrect = result["incorrect"]
    percentage = result["percentage"]

    return {
        "success": True,
        "attempted": attempted,
        "correct": correct,
        "partial": partial,
        "incorrect": incorrect,
        "percentage": percentage,
        "message": (
            f"You attempted {attempted} questions. "
            f"You got {correct} completely correct"
            + (
                f", {partial} partially correct"
                if partial
                else ""
            )
            + (
                f", and {incorrect} incorrect"
                if incorrect
                else ""
            )
            + f". Your score is {percentage}%."
        ),
    }