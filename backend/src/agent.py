from __future__ import annotations

import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    cli,
    function_tool,
    room_io,
    tokenize,
)
from livekit.plugins import (
    deepgram,
    google,
    murf,
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from .database import initialize_database
from .memory import lookup_user_memory, save_user_memory
from .tools import (
    find_next_exercise,
    format_session_score,
    score_and_record_answer,
    start_score_session,
)

logger = logging.getLogger("agent")

load_dotenv(".env.local")


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
IDENTITY

You are ShikshaMitra AI, a friendly and intelligent AI learning
assistant built using Murf Falcon for the VoiceForBharat Edition.

Your goal is to help learners understand concepts, practice questions,
improve spoken English, and build confidence through natural voice
conversations.

You are a personal learning companion, not just an answer machine.

============================================================
SUPPORTED LEARNING AREAS
============================================================

You can help with:

- Computer Science
- Python
- Programming
- Mathematics
- Science
- English grammar
- Spoken English
- Vocabulary
- General Knowledge
- Technology
- Logical reasoning
- Study guidance
- Basic interview preparation

============================================================
DAY 5 LEARNING TOOLS
============================================================

You have these learning tools:

1. fetch_next_exercise
2. score_spoken_answer
3. get_learning_score

IMPORTANT:

When the learner asks for:

- a question
- practice
- quiz
- exercise
- test
- another question
- something to practice

automatically use fetch_next_exercise.

Do NOT invent a question when the exercise tool can provide one.

After the learner answers a fetched exercise:

- automatically use score_spoken_answer
- give natural feedback
- explain the correct answer when necessary
- encourage the learner to continue

Never expose tool names, JSON, database details, or internal
implementation details.

============================================================
SESSION SCORING
============================================================

The current learning session has a score tracker.

Every answered exercise must be recorded through score_spoken_answer.

If the learner says:

- "score me"
- "what is my score?"
- "how did I do?"
- "show my result"
- "tell me my score"
- "how many did I get right?"

automatically call get_learning_score.

Then give a simple natural summary.

Example:

"You attempted 3 questions. You got 2 correct and 1 incorrect.
Your score is 66.7 percent."

Do NOT invent a score.

Do NOT calculate the score from memory manually if the score tool
is available.

If no questions have been attempted:

"You haven't attempted any questions yet. Would you like to start?"

============================================================
EXERCISE FLOW
============================================================

When the learner asks for practice:

1. Identify the requested topic and level if available.
2. Use fetch_next_exercise.
3. Ask the returned question naturally.
4. Wait for the learner's answer.
5. Use score_spoken_answer.
6. Give short feedback.
7. Ask whether they want another question.

Example:

Learner:
"I want to practice Computer Science."

Assistant:
"Sure! Let's practice Computer Science. Here's your first question:
What does CPU stand for?"

After the answer:

"Good try! CPU stands for Central Processing Unit.
Would you like another Computer Science question?"

============================================================
ANSWER EVALUATION
============================================================

Always evaluate the learner's actual answer.

Do not assume an answer is correct just because it sounds confident.

If the answer is correct:
- praise briefly
- explain if useful

If the answer is partially correct:
- acknowledge what was right
- explain what is missing

If the answer is incorrect:
- never shame the learner
- give the correct answer
- explain it simply

Never say the learner is stupid, weak, or bad at the subject.

============================================================
LANGUAGE & SCRIPT
============================================================

Always mirror the learner's language.

English:
Reply in English.

Hindi:
Reply in Hindi using Devanagari script.

Example:
"नमस्ते! आज आप क्या सीखना चाहते हैं?"

Never write Hindi completely in Roman English.

Incorrect:
"Namaste! Aaj aap kya seekhna chahte hain?"

Hinglish:
Use natural Hindi + English, but Hindi words must use Devanagari.

Example:
"आज हम Computer Science का एक question practice करेंगे।"

Do not write:
"Aaj hum Computer Science ka ek question practice karenge."

For technical terms such as:
Python, CPU, RAM, HTML, CSS, SQL, AI, API

keep the standard technical spelling.

If the learner switches language, smoothly switch with them.

============================================================
PERSISTENT MEMORY
============================================================

You have persistent learner memory.

Memory tools:

- lookup_user_memory
- save_user_memory

Useful information may include:

- learner name
- preferred language
- learning level
- current topic
- topics covered
- learning progress

Never ask the learner for their internal user ID.

The application provides the learner ID automatically.

Never invent learner information.

Never claim to remember something unless memory actually provides it.

Only save information after clear learner consent.

If the learner says NO:
- do not save anything

If the learner's answer is unclear:
- ask again

Never store:

- passwords
- API keys
- government IDs
- financial information
- medical records
- sensitive personal information

============================================================
RETURNING LEARNER
============================================================

If memory exists, greet the learner naturally.

Example:

"Welcome back, Shubham! Last time we were working on Python.
Would you like to continue or try something new?"

Do not expose database fields or technical details.

If no memory exists, treat the learner as new.

============================================================
TEACHING STYLE
============================================================

Teach like a friendly personal teacher.

- Keep explanations simple.
- Use practical examples.
- Break difficult concepts into steps.
- Encourage the learner.
- Correct mistakes politely.
- Adapt to the learner's level.
- Ask short follow-up questions.
- Encourage independent thinking.

For voice conversations:

- Keep replies around 2–4 short sentences.
- Avoid long paragraphs.
- Sound natural.
- Do not sound like a textbook.
- Avoid unnecessary technical jargon.

============================================================
PYTHON / PROGRAMMING
============================================================

For programming:

- explain the logic first
- use simple examples
- explain errors clearly
- avoid unnecessary complexity
- encourage understanding instead of blind copying

============================================================
MATHEMATICS
============================================================

For mathematics:

- explain step by step
- show important reasoning
- use simple examples
- encourage the learner to try similar problems

============================================================
COMPUTER SCIENCE
============================================================

For Computer Science:

Focus on beginner-friendly topics such as:

- CPU
- RAM
- ROM
- binary numbers
- algorithms
- data structures
- operating systems
- networking
- databases
- HTML
- basic programming concepts

Use simple real-world examples whenever possible.

============================================================
GUARDRAILS
============================================================

Never:

- shame the learner
- insult the learner
- discourage the learner
- diagnose learning disabilities
- help with cheating
- provide active exam answers
- generate fake certificates
- generate fake academic documents
- store sensitive information

Help the learner understand concepts instead.

============================================================
FIRST GREETING
============================================================

For a completely new learner:

"Hello! I'm ShikshaMitra AI, your personal learning assistant
built using Murf Falcon for the VoiceForBharat Edition.

I can help you learn Computer Science, Python, Maths, Science,
and spoken English. You can speak with me in English, Hindi,
or Hinglish. What would you like to learn today?"
"""


# ============================================================
# ASSISTANT
# ============================================================

class Assistant(Agent):

    def __init__(
        self,
        user_id: str,
        prior_memory: str | None = None,
    ) -> None:

        self.user_id = user_id

        # Avoid repeating exercises in the same call.
        self.used_exercise_ids: list[int] = []

        instructions = SYSTEM_PROMPT

        if prior_memory:
            instructions += (
                "\n\nRETURNING LEARNER CONTEXT:\n"
                + prior_memory
            )

        super().__init__(
            instructions=instructions
        )

    # ========================================================
    # MEMORY LOOKUP
    # ========================================================

    @function_tool
    async def lookup_user_memory(
        self,
        context: RunContext,
    ):
        """
        Look up persistent learning memory for the current learner.
        """

        try:
            return lookup_user_memory(
                self.user_id
            )

        except Exception:
            logger.exception(
                "Memory lookup failed"
            )

            return {
                "success": False,
                "message": (
                    "Memory is temporarily unavailable. "
                    "Continue normally."
                ),
            }

    # ========================================================
    # SAVE MEMORY
    # ========================================================

    @function_tool
    async def save_user_memory(
        self,
        context: RunContext,
        name: str | None = None,
        language_preference: str | None = None,
        learning_level: str | None = None,
        current_topic: str | None = None,
        topics_covered: list[str] | None = None,
    ):
        """
        Save useful learner information only after explicit consent.
        """

        facts: dict[str, object] = {}

        if learning_level:
            facts["learning_level"] = (
                learning_level
            )

        if current_topic:
            facts["current_topic"] = (
                current_topic
            )

        if topics_covered:
            facts["topics_covered"] = (
                topics_covered
            )

        try:

            result = save_user_memory(
                self.user_id,
                name,
                language_preference,
                facts,
            )

            return result

        except Exception:

            logger.exception(
                "Memory save failed"
            )

            return (
                "Memory could not be saved. "
                "Do not claim that it was saved."
            )

    # ========================================================
    # FETCH EXERCISE
    # ========================================================

    @function_tool
    async def fetch_next_exercise(
        self,
        context: RunContext,
        learning_level: str | None = None,
        current_topic: str | None = None,
    ):
        """
        Fetch the next suitable learning exercise.

        Use this whenever the learner asks for a question,
        quiz, exercise, practice, or another question.
        """

        try:

            # If information is missing, try learner memory.
            if (
                learning_level is None
                or current_topic is None
            ):

                memory_result = (
                    lookup_user_memory(
                        self.user_id
                    )
                )

                if isinstance(
                    memory_result,
                    dict,
                ):

                    facts = (
                        memory_result.get(
                            "facts",
                            {},
                        )
                        or {}
                    )

                    if learning_level is None:
                        learning_level = (
                            facts.get(
                                "learning_level"
                            )
                        )

                    if current_topic is None:
                        current_topic = (
                            facts.get(
                                "current_topic"
                            )
                        )

            # If absolutely nothing is known,
            # use a beginner/general exercise.
            if not learning_level:
                learning_level = "beginner"

            if not current_topic:
                current_topic = "computer science"

            result = find_next_exercise(
                learning_level,
                current_topic,
                self.used_exercise_ids,
            )

            if (
                result.get("success")
                and result.get("exercise")
            ):

                exercise_id = result[
                    "exercise"
                ].get("id")

                if (
                    exercise_id is not None
                    and exercise_id
                    not in self.used_exercise_ids
                ):
                    self.used_exercise_ids.append(
                        exercise_id
                    )

            return result

        except Exception:

            logger.exception(
                "Exercise fetch failed"
            )

            return {
                "success": False,
                "error": "tool_failure",
                "message": (
                    "I couldn't fetch a practice "
                    "question right now. "
                    "Let's try again."
                ),
            }

    # ========================================================
    # SCORE SPOKEN ANSWER
    # ========================================================

    @function_tool
    async def score_spoken_answer(
        self,
        context: RunContext,
        question: str,
        expected_answer: str,
        learner_answer: str,
    ):
        """
        Evaluate the learner's spoken answer and record it
        in the current learning session score.

        Use this immediately after the learner answers
        a fetched exercise.
        """

        try:

            result = score_and_record_answer(
                session_id=self.user_id,
                question=question,
                expected_answer=expected_answer,
                learner_answer=learner_answer,
            )

            return result

        except Exception:

            logger.exception(
                "Answer scoring failed"
            )

            return {
                "success": False,
                "score": 0.0,
                "correct": False,
                "feedback": (
                    "I couldn't score that answer "
                    "right now. Let's try again."
                ),
            }

    # ========================================================
    # GET SCORE
    # ========================================================

    @function_tool
    async def get_learning_score(
        self,
        context: RunContext,
    ):
        """
        Return the learner's current score for this session.

        Use when the learner asks for their score,
        result, performance, or how they did.
        """

        try:

            result = format_session_score(
                self.user_id
            )

            return result

        except Exception:

            logger.exception(
                "Score lookup failed"
            )

            return {
                "success": False,
                "message": (
                    "I couldn't calculate your score "
                    "right now."
                ),
            }


# ============================================================
# SERVER
# ============================================================

server = AgentServer()


# ============================================================
# PREWARM
# ============================================================

def prewarm(proc: JobProcess):

    initialize_database()

    proc.userdata["vad"] = (
        silero.VAD.load()
    )


server.setup_fnc = prewarm


# ============================================================
# AGENT SESSION
# ============================================================

@server.rtc_session(
    agent_name="my-agent"
)
async def my_agent(
    ctx: JobContext,
):

    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # --------------------------------------------------------
    # Connect to LiveKit
    # --------------------------------------------------------

    await ctx.connect()

    participant = (
        await ctx.wait_for_participant()
    )

    learner_id = participant.identity

    logger.info(
        "Learner connected: %s",
        learner_id,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Start a NEW score for every call.
    # Day 5 score belongs to the current session.
    # --------------------------------------------------------

    start_score_session(
        learner_id
    )

    # --------------------------------------------------------
    # Load persistent memory
    # --------------------------------------------------------

    prior_memory = None

    try:

        memory_record = (
            lookup_user_memory(
                learner_id
            )
        )

        if isinstance(
            memory_record,
            dict,
        ):

            facts = (
                memory_record.get(
                    "facts",
                    {},
                )
                or {}
            )

            name = (
                memory_record.get(
                    "name"
                )
            )

            language = (
                memory_record.get(
                    "language_preference"
                )
            )

            level = facts.get(
                "learning_level"
            )

            topic = facts.get(
                "current_topic"
            )

            topics = facts.get(
                "topics_covered"
            )

            memory_lines = []

            if name:
                memory_lines.append(
                    f"Learner name: {name}"
                )

            if language:
                memory_lines.append(
                    f"Preferred language: {language}"
                )

            if level:
                memory_lines.append(
                    f"Learning level: {level}"
                )

            if topic:
                memory_lines.append(
                    f"Current topic: {topic}"
                )

            if isinstance(
                topics,
                list,
            ) and topics:

                memory_lines.append(
                    "Topics covered: "
                    + ", ".join(
                        str(topic)
                        for topic in topics
                    )
                )

            if memory_lines:

                prior_memory = (
                    "The learner has previous "
                    "learning memory. Use it naturally "
                    "without exposing technical details.\n"
                    + "\n".join(
                        memory_lines
                    )
                )

    except Exception:

        logger.exception(
            "Failed to load learner memory"
        )

    # --------------------------------------------------------
    # Create assistant
    # --------------------------------------------------------

    assistant = Assistant(
        user_id=learner_id,
        prior_memory=prior_memory,
    )

    # --------------------------------------------------------
    # Voice AI pipeline
    # --------------------------------------------------------

    session = AgentSession(

        # Speech-to-text
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
        ),

        # LLM
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),

        # Murf Falcon
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(
                min_sentence_len=2
            ),
            text_pacing=True,
        ),

        # Multilingual turn detection
        turn_detection=MultilingualModel(),

        # Voice activity detection
        vad=ctx.proc.userdata["vad"],

        # Generate responses early
        preemptive_generation=True,
    )

    # --------------------------------------------------------
    # Start session
    # --------------------------------------------------------

    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if (
                        params.participant.kind
                        == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    )
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    logger.info(
        "ShikshaMitra AI session started for %s",
        learner_id,
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    cli.run_app(server)