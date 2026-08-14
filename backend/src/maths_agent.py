from __future__ import annotations

import logging
from typing import Any

from livekit.agents import (
    Agent,
    RunContext,
    function_tool,
    tokenize,
    tts,
)
from livekit.plugins import murf

try:
    from .call_analytics import mark_exercise_completed
    from .escalation import create_escalation_record
    from .tools import (
        find_next_exercise,
        format_session_score,
        score_and_record_answer,
    )
except ImportError:
    from src.call_analytics import mark_exercise_completed
    from src.escalation import create_escalation_record
    from src.tools import (
        find_next_exercise,
        format_session_score,
        score_and_record_answer,
    )

logger = logging.getLogger("agent.maths_specialist")

# Murf Falcon Male Voice configuration for Maths Practice Specialist (friendly, calm, clear Indian male tutor)
MATHS_SPECIALIST_VOICE = "Samar"


# ============================================================
# MATHS SPECIALIST SYSTEM PROMPT
# ============================================================

MATHS_SPECIALIST_PROMPT = """
IDENTITY & ROLE

You are the dedicated Maths Practice Specialist for ShikshaMitra AI,
built using Murf Falcon for the VoiceForBharat Edition.

Your ONLY job is interactive Mathematics teaching and practice.
You are a focused, patient, supportive, encouraging, and teacher-like personal Maths tutor.

============================================================
MULTILINGUAL LANGUAGE & SCRIPT RULES (CRITICAL)
============================================================

You are a MULTILINGUAL Maths Specialist and must automatically detect and respond in the SAME LANGUAGE used by the learner.

1. HINDI INPUT:
   - If the learner speaks Hindi (in Devanagari script or spoken Hindi):
     → Respond in Hindi using Devanagari script.
   - Example:
     Learner: "मुझे percentage समझाइए।"
     Specialist: "ज़रूर! चलिए percentage को एक आसान example से समझते हैं।"

2. ENGLISH INPUT:
   - If the learner speaks English:
     → Respond completely in clear, friendly English.
   - Example:
     Learner: "I want to practice percentages."
     Specialist: "Sure! Let's start practicing percentages."
   - Example:
     Learner: "Can you explain fractions?"
     Specialist: "Sure! Let's understand fractions step by step."

3. HINGLISH / ROMANIZED HINDI INPUT:
   - If the learner speaks Hinglish or Romanized Hindi:
     → Understand the Hinglish input accurately.
     → Respond in Hindi using Devanagari script.
   - Example:
     Learner: "Mujhe percentage ke questions practice karne hain."
     Specialist: "ज़रूर! चलिए percentage की practice शुरू करते हैं।"
   - CRITICAL: NEVER USE ROMANIZED HINDI (Hinglish written in Latin script) in your response!
     * NEVER respond like: "Chaliye percentage ki practice shuru karte hain."
     * NEVER respond like: "Aap pehle iska answer try kijiye."
     * ALWAYS respond in Devanagari script: "चलिए percentage की practice शुरू करते हैं।"

4. DYNAMIC LANGUAGE SWITCHING:
   - If the learner switches language mid-conversation or explicitly requests a language switch:
     → Switch naturally and immediately to the learner's requested/current language.
   - Example:
     Learner: "मुझे percentage समझाइए।"
     Specialist: "ज़रूर! पहले एक आसान सवाल करते हैं।"
     Learner: "Can you explain that in English?" or "Please explain this in English."
     Specialist: "Of course! Let me explain it in English."

5. MIXED HINDI + ENGLISH MATHEMATICAL TERMINOLOGY:
   - If the learner uses mixed Hindi + English mathematical terms (e.g., "Percentage ka formula kya hota hai?"):
     → Respond naturally in Devanagari Hindi incorporating standard English mathematical terms.
   - Example:
     Learner: "Percentage ka formula batao."
     Specialist: "Percentage निकालने का basic formula है:
     Percentage = (Part / Whole) * 100."
   - Common English math terms to use naturally in Hindi responses: percentage, fraction, decimal, algebra, equation, formula, variable, step-by-step, answer, calculate, solve, perimeter, area, ratio.

6. DYNAMIC DETECTION & CONTEXT:
   - Detect the language dynamically from the learner's CURRENT message and conversation context.
   - Do NOT force Hindi when the learner speaks English.
   - Do NOT force English when the learner speaks Hindi or Hinglish.
   - Always prioritize the learner's language preference.

7. DEVANAGARI VOCABULARY STANDARDS (WHEN RESPONDING IN HINDI):
   - Always use proper Devanagari Hindi words:
     "आप", "चलिए", "समझिए", "कीजिए", "बताइए", "सवाल", "उत्तर", "बिल्कुल", "ज़रूर"

============================================================
TEACHING BEHAVIOR & INTERACTIVE LOOP
============================================================

- Teach concepts simply and clearly.
- Be patient, encouraging, teacher-like, and interactive.
- Ask ONE question at a time. Step-by-step guidance.
- NEVER dump long textbook explanations or multiple questions at once.
- Let the learner attempt their answer.
- Give hints before answers when the learner is struggling.
- Evaluate the answer carefully using `score_maths_answer`.
- If the learner is CORRECT:
  * Praise warmly (e.g., "बहुत बढ़िया! बिल्कुल सही जवाब। 🎉" or "Great job! That is absolutely correct. 🎉").
  * Briefly highlight why it's right, then move to the next question.
- If the learner is INCORRECT or STRUGGLING:
  * Never judge or criticize.
  * Give a gentle hint first (e.g., "कोई बात नहीं। एक छोटा सा hint देता हूँ..." or "No problem! Here's a small hint...").
  * Let the learner try again.
  * If they still struggle, show the step-by-step solution calmly.
- Adapt difficulty gradually:
  * Level 1: Basic concept / direct calculation (e.g., 20% of 100)
  * Level 2: Medium calculation (e.g., 25% of 240)
  * Level 3: Multi-step calculation (e.g., 15% of 360)
  * Level 4: Practical word problem

============================================================
SUPPORTED TOPICS
============================================================

- Arithmetic (Addition, Subtraction, Multiplication, Division)
- Fractions, Decimals, Percentages, Ratios & Proportions
- Basic Algebra, Linear Equations, Variables
- Basic Geometry (Shapes, Perimeter, Area, Angles)
- Word Problems & Practical Math
- Number Systems & Basic Statistics (Mean, Median, Mode)

============================================================
STRICT SPECIALIZATION BOUNDARIES (OUT-OF-DOMAIN HANDLING)
============================================================

You are ONLY a Maths Specialist.
You must NOT answer non-Maths subjects such as:
- Python / Programming
- Computer Science / Technology
- Science / Physics / Chemistry / Biology
- English Grammar / Spoken English
- General Knowledge / History / Geography

If the learner asks about any of these non-Maths subjects:
1. Explain politely in 1 short sentence (in the learner's language) that ShikshaMitra's main assistant handles that subject.
2. Example (Hindi): "ज़रूर! Python और programming के लिए मैं आपको वापस ShikshaMitra के main learning assistant से connect करता हूँ।"
3. Example (English): "Sure! For Python and programming, I'll connect you back to ShikshaMitra's main learning assistant."
4. Immediately call the tool `handoff_to_main_agent`.

============================================================
HUMAN TEACHER HELP (DAY 7 ESCALATION)
============================================================

If the learner is severely frustrated, distressed, or explicitly asks for a human teacher (e.g., "मुझे शिक्षक से बात करनी है", "I want to talk to a teacher"):
1. Acknowledge their feeling calmly.
2. Ask for explicit consent to request human teacher assistance.
3. If they agree (YES), call `create_escalation` and give them their reference ID.
4. If they say NO, continue helping them patiently.
"""


# ============================================================
# MATHS PRACTICE AGENT CLASS
# ============================================================


class MathsPracticeAgent(Agent):
    """
    Dedicated Maths Practice Specialist Agent for Day 9.
    Provides focused, interactive, step-by-step Mathematics practice
    multilingually in the learner's preferred language (English or Devanagari Hindi).
    """

    def __init__(
        self,
        user_id: str,
        topic: str = "Mathematics",
        initial_context: str = "",
        learning_level: str = "beginner",
        call_id: str | None = None,
        language_preference: str = "Hindi",
        tts_instance: tts.TTS | None = None,
    ) -> None:
        self.user_id = user_id
        self.topic = topic or "Mathematics"
        self.initial_context = initial_context
        self.learning_level = learning_level
        self.call_id = call_id
        self.language_preference = language_preference
        self.used_exercise_ids: list[int] = []

        context_prompt = (
            f"\n\nCURRENT PRACTICE SESSION CONTEXT:\n"
            f"- Requested Topic: {self.topic}\n"
            f"- Initial Learner Request: {self.initial_context or self.topic}\n"
            f"- Learner Level: {self.learning_level}\n"
            f"- Language Preference: {self.language_preference}\n"
            f"IMPORTANT: The learner was already interacting with the main agent and specifically requested "
            f"Maths practice on '{self.topic}'. Continue immediately with this topic in the learner's language. "
            f"DO NOT ask them what topic they want to learn or ask them to repeat their request."
        )

        full_instructions = MATHS_SPECIALIST_PROMPT + context_prompt

        # Dedicated Murf Falcon Male Voice for Maths Practice Specialist
        if tts_instance is None:
            tts_instance = murf.TTS(
                voice=MATHS_SPECIALIST_VOICE,
                style="Conversation",
                tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
                text_pacing=True,
            )

        super().__init__(instructions=full_instructions, tts=tts_instance)

    async def on_enter(self) -> None:
        """
        Called when the session transitions to this Maths Practice Specialist.
        Speaks a warm, brief introduction and immediately launches into the requested topic in the learner's language.
        """
        logger.info(
            "[MATHS SPECIALIST] Entered session for user=%s, topic=%s",
            self.user_id,
            self.topic,
        )

        # Generate the opening introduction + first practice question directly in the learner's language
        intro_instructions = (
            f"You have just taken over the conversation as the Maths Practice Specialist. "
            f"The learner requested: '{self.initial_context or self.topic}'. "
            f"Introduce yourself briefly in the same language as the learner's request: "
            f"- If the request is in English: 'Hello! I am ShikshaMitra's Maths Practice Specialist. "
            f"Let's start step-by-step practice on {self.topic}.' followed immediately by the first beginner practice question in English (e.g. 'First question: What is 25% of 240?'). "
            f"- If the request is in Hindi or Hinglish: 'नमस्ते! मैं ShikshaMitra का Maths Practice Specialist हूँ। "
            f"चलिए {self.topic} की step-by-step practice शुरू करते हैं।' followed immediately by the first beginner practice question in Hindi Devanagari (e.g. 'पहला सवाल: 240 का 25% कितना होगा?'). "
            f"Do not ask the user to repeat their question."
        )

        try:
            self.session.generate_reply(instructions=intro_instructions)
        except Exception:
            logger.exception("[MATHS SPECIALIST] Failed to generate enter reply")

    # ========================================================
    # FETCH MATHS EXERCISE
    # ========================================================

    @function_tool
    async def fetch_maths_exercise(
        self,
        context: RunContext,
        topic: str | None = None,
        difficulty: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch a curated mathematics practice exercise from the question bank.

        Parameters:
            topic: Specific maths topic (e.g. percentage, fractions, algebra, arithmetic, geometry).
            difficulty: beginner, intermediate, or advanced.
        """
        chosen_topic = topic or self.topic or "mathematics"
        chosen_level = difficulty or self.learning_level or "beginner"

        try:
            result = find_next_exercise(
                chosen_level,
                chosen_topic,
                self.used_exercise_ids,
            )

            if result.get("success") and result.get("exercise"):
                exercise_id = result["exercise"].get("id")
                if (
                    exercise_id is not None
                    and exercise_id not in self.used_exercise_ids
                ):
                    self.used_exercise_ids.append(exercise_id)

            return result
        except Exception:
            logger.exception("[MATHS SPECIALIST] Exercise fetch failed")
            return {
                "success": False,
                "error": "fetch_failed",
                "message": "Practice question fetch failed. Generate a suitable question directly.",
            }

    # ========================================================
    # SCORE MATHS ANSWER
    # ========================================================

    @function_tool
    async def score_maths_answer(
        self,
        context: RunContext,
        question: str,
        expected_answer: str,
        learner_answer: str,
    ) -> dict[str, Any]:
        """
        Evaluate the learner's spoken mathematics answer, score it, and record it in the session.

        Parameters:
            question: The mathematics question asked.
            expected_answer: The correct numerical/mathematical solution.
            learner_answer: The learner's spoken answer.
        """
        logger.info(
            "[MATHS SPECIALIST] Scoring answer: Q='%s', Expected='%s', Learner='%s'",
            question,
            expected_answer,
            learner_answer,
        )

        try:
            result = score_and_record_answer(
                session_id=self.user_id,
                question=question,
                expected_answer=expected_answer,
                learner_answer=learner_answer,
            )

            if result.get("correct") and self.call_id:
                mark_exercise_completed(self.call_id)

            return result
        except Exception:
            logger.exception("[MATHS SPECIALIST] Scoring failed")
            return {
                "success": False,
                "score": 0.0,
                "correct": False,
                "feedback": "Answer scoring temporarily unavailable. Evaluate the answer directly.",
            }

    # ========================================================
    # GET MATHS SCORE
    # ========================================================

    @function_tool
    async def get_maths_score(
        self,
        context: RunContext,
    ) -> dict[str, Any]:
        """Return the learner's current score and exercise statistics for this session."""
        try:
            return format_session_score(self.user_id)
        except Exception:
            logger.exception("[MATHS SPECIALIST] Score lookup failed")
            return {
                "success": False,
                "message": "Score lookup temporarily unavailable.",
            }

    # ========================================================
    # HANDOFF BACK TO MAIN AGENT
    # ========================================================

    @function_tool
    async def handoff_to_main_agent(
        self,
        context: RunContext,
        reason: str,
        topic: str = "",
    ) -> dict[str, Any]:
        """
        Hand the conversation back to the main ShikshaMitra learning assistant.

        Use this tool when the learner asks about non-Maths subjects such as:
        - Python / Programming / Computer Science
        - Science / Physics / Chemistry / Biology
        - English Grammar / Spoken English
        - General Knowledge / Technology
        - Or explicitly asks to return to the main assistant

        Parameters:
            reason: Why the handoff back is happening (e.g. "Learner wants to learn Python").
            topic: The non-Maths topic requested (e.g. "Python", "Science", "General").
        """
        logger.info(
            "[HANDOFF BACK] Transferring from Maths Specialist to Main Agent. Reason='%s', Topic='%s'",
            reason,
            topic,
        )

        try:
            # Import Assistant dynamically to avoid circular import
            try:
                from .agent import Assistant
            except ImportError:
                from src.agent import Assistant

            main_assistant = Assistant(
                user_id=self.user_id,
                call_id=self.call_id,
            )

            # Perform real LiveKit Agent handoff back to main agent
            self.session.update_agent(main_assistant)

            return {
                "success": True,
                "message": (
                    f"Successfully returning to main ShikshaMitra assistant for '{topic or reason}'."
                ),
            }
        except Exception as e:
            logger.exception("[HANDOFF BACK] Return handoff failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "message": "Return handoff failed. Let me continue helping you.",
            }

    # ========================================================
    # CREATE ESCALATION — DAY 7 INTEGRATION
    # ========================================================

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        reason: str,
        summary: str,
        already_checked: str = "",
        urgency: str = "MEDIUM",
        language: str = "Hindi",
        preferred_follow_up: str = "voice",
        learner_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a human teacher help request if the student is struggling or explicitly asks for a teacher.

        Only call this tool AFTER obtaining clear, explicit student consent.
        """
        logger.info(
            "[MATHS SPECIALIST ESCALATION] Human help needed: Reason=%s, Language=%s",
            reason,
            language,
        )

        try:
            result = create_escalation_record(
                learner_id=self.user_id,
                reason=reason,
                summary=summary,
                already_checked=already_checked or f"Maths practice on {self.topic}",
                urgency=urgency,
                language=language,
                preferred_follow_up=preferred_follow_up,
                learner_name=learner_name,
            )
            return result
        except Exception:
            logger.exception("[MATHS SPECIALIST ESCALATION] Escalation failed")
            return {
                "success": False,
                "message": "Teacher help request could not be created right now.",
            }
