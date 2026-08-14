"""
Day 9 - Maths Practice Specialist & Multi-Agent Architecture Tests

Validates:
1. MathsPracticeAgent instantiation, instructions, role, and Devanagari Hindi rules.
2. Context preservation from Main Agent to Maths Specialist.
3. Main Agent handoff tool (handoff_to_maths_specialist) presence and parameters.
4. Maths Specialist scoring and Day 8 call analytics integration.
5. Maths Specialist return handoff (handoff_to_main_agent).
6. Day 7 teacher help escalation compatibility inside Maths Specialist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from livekit.agents import AgentSession, inference, llm

# Ensure backend root is in sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from src.agent import Assistant  # noqa: E402
from src.call_analytics import (  # noqa: E402
    get_analytics_summary,
    initialize_call_analytics_table,
    start_call_record,
)
from src.database import initialize_database  # noqa: E402
from src.escalation import initialize_escalation_table  # noqa: E402
from src.maths_agent import (  # noqa: E402
    MATHS_SPECIALIST_PROMPT,
    MATHS_SPECIALIST_VOICE,
    MathsPracticeAgent,
)


def _llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")


@pytest.fixture(autouse=True)
def _init_db():
    """Ensure database tables exist before each test."""
    initialize_database()
    initialize_escalation_table()
    initialize_call_analytics_table()


# ============================================================
# SPECIALIST CREATION & PROMPT TESTS
# ============================================================


def test_maths_agent_initialization():
    """Verify MathsPracticeAgent initializes with proper instructions and context."""
    agent = MathsPracticeAgent(
        user_id="learner-test-1",
        topic="percentage",
        initial_context="Mujhe percentage ke questions practice karne hain",
        learning_level="beginner",
    )

    assert agent.user_id == "learner-test-1"
    assert agent.topic == "percentage"
    assert agent.learning_level == "beginner"
    assert "Maths Practice Specialist" in agent.instructions
    assert "Devanagari" in agent.instructions
    assert "percentage" in agent.instructions
    assert "NEVER USE ROMANIZED HINDI" in agent.instructions


def test_maths_agent_male_voice_configuration():
    """Verify MathsPracticeAgent uses the dedicated Murf Falcon male voice."""
    agent = MathsPracticeAgent(
        user_id="learner-voice-test",
        topic="arithmetic",
    )

    assert MATHS_SPECIALIST_VOICE == "Samar"
    assert agent._tts is not None
    assert getattr(agent._tts, "_opts", None) is not None
    assert agent._tts._opts.voice == "Samar"


def test_maths_agent_devanagari_rules():
    """Verify system prompt strictly mandates multilingual handling, Devanagari Hindi, and provides examples."""
    prompt = MATHS_SPECIALIST_PROMPT
    assert "MULTILINGUAL LANGUAGE & SCRIPT RULES" in prompt
    assert "NEVER USE ROMANIZED HINDI" in prompt
    assert "DYNAMIC LANGUAGE SWITCHING" in prompt
    assert "MIXED HINDI + ENGLISH MATHEMATICAL TERMINOLOGY" in prompt
    assert "आप" in prompt
    assert "चलिए" in prompt
    assert "समझिए" in prompt
    assert "कीजिए" in prompt
    assert "बताइए" in prompt


def test_maths_agent_supported_topics():
    """Verify supported mathematics topics are documented in the prompt."""
    prompt = MATHS_SPECIALIST_PROMPT
    assert "Arithmetic" in prompt
    assert "Fractions" in prompt
    assert "Percentages" in prompt
    assert "Algebra" in prompt
    assert "Geometry" in prompt


def test_maths_agent_out_of_domain_handling():
    """Verify prompt instructs return handoff for non-maths subjects."""
    prompt = MATHS_SPECIALIST_PROMPT
    assert "STRICT SPECIALIZATION BOUNDARIES" in prompt
    assert "Python / Programming" in prompt
    assert "handoff_to_main_agent" in prompt


# ============================================================
# CONTEXT PRESERVATION TESTS
# ============================================================


def test_context_preservation_in_instructions():
    """Verify user query context is directly injected so specialist knows the exact topic."""
    user_query = "Mujhe percentage ke 5 questions practice karne hain"
    agent = MathsPracticeAgent(
        user_id="learner-ctx-1",
        topic="percentage",
        initial_context=user_query,
    )

    assert user_query in agent.instructions
    assert "DO NOT ask them what topic they want to learn" in agent.instructions


# ============================================================
# MAIN AGENT HANDOFF TOOL TESTS
# ============================================================


def test_main_agent_has_handoff_tool():
    """Verify Main Agent (Assistant) exposes handoff_to_maths_specialist tool."""
    assistant = Assistant(user_id="learner-test-main")
    tool_names = [
        getattr(tool, "id", getattr(tool, "name", str(tool)))
        for tool in assistant.tools
    ]

    assert "handoff_to_maths_specialist" in tool_names
    assert "create_escalation" in tool_names
    assert "fetch_next_exercise" in tool_names
    assert "score_spoken_answer" in tool_names


def test_main_agent_system_prompt_handoff_guidance():
    """Verify Main Agent system prompt provides clear instructions on when to handoff."""
    assistant = Assistant(user_id="test-prompt-user")
    instructions = assistant.instructions

    assert "DAY 9 — MATHS PRACTICE SPECIALIST HANDOFF" in instructions
    assert "MathsPracticeAgent" in instructions
    assert "WHEN TO HANDOFF" in instructions
    assert "WHEN NOT TO HANDOFF" in instructions
    assert "handoff_to_maths_specialist" in instructions


# ============================================================
# MATHS SPECIALIST TOOLS & SCORING TESTS
# ============================================================


def test_maths_specialist_tool_set():
    """Verify MathsPracticeAgent has dedicated maths tools and escalation tool."""
    agent = MathsPracticeAgent(user_id="learner-tools-1", topic="algebra")
    tool_names = [
        getattr(tool, "id", getattr(tool, "name", str(tool))) for tool in agent.tools
    ]

    assert "score_maths_answer" in tool_names
    assert "get_maths_score" in tool_names
    assert "fetch_maths_exercise" in tool_names
    assert "handoff_to_main_agent" in tool_names
    assert "create_escalation" in tool_names


@pytest.mark.asyncio
async def test_maths_scoring_and_analytics_integration():
    """Verify score_maths_answer evaluates correctly and updates Day 8 call analytics."""
    call_id = "test-maths-call-001"
    start_call_record(call_id=call_id, learner_id="learner-score-test")

    agent = MathsPracticeAgent(
        user_id="learner-score-test",
        topic="percentage",
        call_id=call_id,
    )

    # Score a correct answer: 25% of 240 = 60
    result = await agent.score_maths_answer(
        context=None,
        question="240 ka 25% kitna hoga?",
        expected_answer="60",
        learner_answer="60",
    )

    assert result["success"] is True
    assert result["correct"] is True
    assert result["score"] == 1.0

    # Verify Day 8 Call Analytics recorded exercise completion
    summary = get_analytics_summary()
    assert summary["total_calls"] >= 1


@pytest.mark.asyncio
async def test_maths_specialist_escalation_integration():
    """Verify Day 7 Teacher Escalation works from within MathsPracticeAgent."""
    agent = MathsPracticeAgent(
        user_id="learner-esc-maths",
        topic="fractions",
    )

    result = await agent.create_escalation(
        context=None,
        reason="Frustrated Learner",
        summary="Learner is struggling with fraction simplification",
        urgency="HIGH",
        language="Hindi",
    )

    assert result["success"] is True
    assert result["status"] == "OPEN"
    assert result["reference_id"].startswith("ESC-")


# ============================================================
# MULTILINGUAL BEHAVIOR & LANGUAGE SWITCHING TESTS
# ============================================================


@pytest.mark.asyncio
async def test_multilingual_case1_hinglish_to_devanagari():
    """TEST 1: Learner speaks Hinglish -> Specialist responds in Hindi (Devanagari script)."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-1",
            topic="percentage",
            initial_context="Mujhe percentage ke questions practice karne hain.",
        )
        await session.start(agent)
        result = await session.run(
            user_input="Mujhe percentage ke questions practice karne hain."
        )

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Responds in Hindi using Devanagari script to help practice percentages.
                Must NOT use Romanized Hindi (Latin alphabet for Hindi words).
                Can include English mathematical terms naturally.
                """,
            )
        )


@pytest.mark.asyncio
async def test_multilingual_case2_english_input():
    """TEST 2: Learner speaks English -> Specialist responds completely in English."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-2",
            topic="percentage",
            initial_context="I want to practice percentages.",
            language_preference="English",
        )
        await session.start(agent)
        result = await session.run(user_input="I want to practice percentages.")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Responds completely in English to start practicing percentages with the learner.
                Must NOT respond in Hindi.
                """,
            )
        )


@pytest.mark.asyncio
async def test_multilingual_case3_devanagari_hindi_input():
    """TEST 3: Learner speaks Hindi in Devanagari -> Specialist responds in Hindi using Devanagari script."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-3",
            topic="fractions",
            initial_context="मुझे fractions समझाइए।",
        )
        await session.start(agent)
        result = await session.run(user_input="मुझे fractions समझाइए।")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Responds in Hindi using Devanagari script explaining or practicing fractions with the learner.
                Must use Devanagari script.
                """,
            )
        )


@pytest.mark.asyncio
async def test_multilingual_case4_english_explanation():
    """TEST 4: Learner asks in English -> Specialist responds in English."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-4",
            topic="fractions",
            initial_context="Can you explain fractions?",
            language_preference="English",
        )
        await session.start(agent)
        result = await session.run(user_input="Can you explain fractions?")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Responds in clear, friendly English to explain or start practicing fractions.
                Must respond in English.
                """,
            )
        )


@pytest.mark.asyncio
async def test_multilingual_case5_mixed_hinglish_formula():
    """TEST 5: Learner asks in mixed Hinglish for formula -> Specialist responds in Devanagari Hindi with natural English math terms."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-5",
            topic="percentage",
            initial_context="Percentage ka formula batao.",
        )
        await session.start(agent)
        result = await session.run(user_input="Percentage ka formula batao.")

        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Responds in Hindi using Devanagari script explaining the percentage formula,
                incorporating standard mathematical terms like formula, percentage, Part, Whole, 100 naturally.
                Must NOT use Romanized Hindi (Latin alphabet for Hindi words).
                """,
            )
        )


@pytest.mark.asyncio
async def test_multilingual_case6_language_switching():
    """TEST 6: Learner starts in Hindi and then says 'Please explain this in English.' -> Specialist switches to English."""
    async with (
        _llm() as llm_instance,
        AgentSession(llm=llm_instance) as session,
    ):
        agent = MathsPracticeAgent(
            user_id="learner-test-ml-6",
            topic="percentage",
            initial_context="मुझे percentage समझाइए।",
        )
        await session.start(agent)

        # First turn in Hindi
        result1 = await session.run(user_input="मुझे percentage समझाइए।")
        await (
            result1.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="Responds in Hindi in Devanagari script regarding percentage.",
            )
        )

        # Second turn switches to English
        result2 = await session.run(user_input="Please explain this in English.")
        await (
            result2.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_instance,
                intent="""
                Switches smoothly to English and explains percentage or provides the next question in English.
                The response MUST be in English.
                """,
            )
        )
