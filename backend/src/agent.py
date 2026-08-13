from __future__ import annotations

import json
import logging
import threading

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
    tokenize,
)
from livekit.plugins import (
    deepgram,
    google,
    murf,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from .call_analytics import (
    end_call_record,
    initialize_call_analytics_table,
    mark_exercise_completed,
    start_call_record,
)
from .dashboard import run_dashboard
from .database import initialize_database
from .escalation import (
    create_escalation_record,
    initialize_escalation_table,
)
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
# CONFIGURATION
# ============================================================


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

1. Use score_spoken_answer.
2. Give natural feedback.
3. Explain the correct answer when useful.
4. Ask whether they want another question.

Never expose tool names, JSON, database details, or internal
implementation details.


============================================================
SESSION SCORING
============================================================

Every answered exercise must be recorded through
score_spoken_answer.

If the learner asks:

- "score me"
- "what is my score?"
- "how did I do?"
- "show my result"
- "tell me my score"
- "how many did I get right?"

automatically call get_learning_score.

Never invent a score.

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


============================================================
ANSWER EVALUATION
============================================================

Always evaluate the learner's actual answer.

Do not assume an answer is correct just because it sounds confident.

If correct:
- praise briefly
- explain if useful

If partially correct:
- acknowledge what was right
- explain what is missing

If incorrect:
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
- do not save anything.

If the learner's answer is unclear:
- ask again.

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

"Welcome back! Last time we were working on Python.
Would you like to continue or try something new?"

Do not expose database fields or technical details.

If no memory exists, treat the learner as new.


============================================================
OUTBOUND CALL — DAY 6
============================================================

This agent can make outbound daily learning practice calls.

The purpose of the outbound call is:

"Daily Learning Practice"

At the beginning of an outbound call:

1. Clearly introduce ShikshaMitra AI.
2. Explain why you are calling.
3. Tell the learner they can ask you to stop future calls.
4. Ask whether this is a good time.

Example:

"Hello, this is ShikshaMitra AI. I'm calling for your daily
learning practice. If you don't want these calls, just tell me
and I'll stop. Is now a good time?"

Do NOT immediately start asking questions.

Wait for the learner to confirm that they are ready.

If the learner says:
- they are busy
- not interested
- stop calling
- don't call again

politely end the conversation.

If the learner agrees:

"Great! Let's do a short learning practice session."

Then ask what they would like to practice, or use their remembered
learning topic when appropriate.

Use the Day 5 exercise tools during the practice.

Keep outbound calls short, friendly, and useful.


============================================================
OUTBOUND CALL BEHAVIOR
============================================================

Outbound calls are different from normal browser conversations.

The learner did not initiate the call.

Therefore:

- Be concise.
- Identify yourself immediately.
- Explain the reason for calling.
- Ask permission to continue.
- Respect "no".
- Never pressure the learner.
- Never repeatedly call during the same session.
- Do not continue if the learner asks to stop.


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
HUMAN HELP POLICY — DAY 7
============================================================

ShikshaMitra should consider requesting human teacher help when:

1. The learner is clearly upset, frustrated, or struggling and
   teacher support would be genuinely useful.

   Examples:
   - "मुझे कुछ समझ नहीं आ रहा।"
   - "मैं बहुत परेशान हो गया हूँ।"
   - "I don't understand this."
   - "I'm getting really frustrated."

2. The learner explicitly asks for a teacher.

   Examples:
   - "मुझे शिक्षक से बात करनी है।"
   - "Can I talk to a teacher?"
   - "मुझे टीचर की मदद चाहिए।"

Before creating an escalation:

- Acknowledge the learner's difficulty.
- Explain why teacher help may be useful.
- Tell the learner what information will be shared
  (a short summary of the problem, nothing private).
- Ask for explicit permission.

Consent rules:

- Only create escalation when the learner clearly says YES.
- Silence is NOT consent.
- "Maybe" is NOT consent.
- If unclear, ask again.
- If the learner says NO, do NOT create any escalation.
  Continue helping normally.

After a successful escalation:

- Give the reference ID to the learner.
- Tell the learner the request status is OPEN.
- Explain the honest next step.
- NEVER promise immediate teacher response unless the system
  actually guarantees it.

Normal learning questions must NEVER trigger an escalation.

"Python में loop क्या होता है?" → answer normally, no escalation.
"Give me a Python question." → continue practice, no escalation.


============================================================
ESCALATION CONSENT LANGUAGE
============================================================

The consent message MUST follow the learner's language.

Hindi:
"मैं आपकी समस्या का एक छोटा सा सारांश शिक्षक के साथ साझा
करके मदद का अनुरोध भेज सकता हूँ। क्या मैं ऐसा करूं?"

English:
"I can share a short summary of your problem with a teacher
and request help. Would you like me to do that?"

Hinglish:
"मैं आपकी problem का एक short summary teacher के साथ share
करके help request भेज सकता हूँ। क्या मैं ऐसा करूं?"

The confirmation message must also follow the language:

Hindi:
"आपका शिक्षक-सहायता अनुरोध बना दिया गया है। आपका reference
ID है ESC-XXXXXX।"

English:
"Your teacher-help request has been created. Your reference ID
is ESC-XXXXXX."

If the learner says NO:

Hindi:
"ठीक है। मैं आपकी जानकारी साझा नहीं करूंगा और कोई
teacher-help request नहीं बनाऊंगा। मैं यहीं आपकी मदद करने
की कोशिश करता हूँ।"

English:
"Okay. I won't share your information or create a teacher-help
request. Let me continue helping you here."


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
        outbound_call: bool = False,
        call_id: str | None = None,
    ) -> None:

        self.user_id = user_id
        self.outbound_call = outbound_call
        self.call_id = call_id

        # Avoid repeating exercises in the same call.
        self.used_exercise_ids: list[int] = []

        instructions = SYSTEM_PROMPT

        if outbound_call:
            instructions += """

OUTBOUND SESSION MODE

This is an outbound daily learning practice call.

When the session begins:
Do not use the standard long first greeting.
Identify ShikshaMitra AI, explain why you are calling, tell the learner they can ask to stop future calls at any time, and ask if now is a good time for a quick practice.

Wait for the learner's response before starting exercises.

If the learner agrees or says yes:
Start a short Computer Science practice session using fetch_next_exercise and score_spoken_answer.

If the learner says no, busy, not interested, or asks to stop calling:
Politely say: "No problem. I won't keep you. Have a great day!" and gracefully end the call.
"""

        if prior_memory:
            instructions += "\n\nRETURNING LEARNER CONTEXT:\n" + prior_memory

        super().__init__(instructions=instructions)

    # ========================================================
    # MEMORY LOOKUP
    # ========================================================

    @function_tool
    async def lookup_user_memory(
        self,
        context: RunContext,
    ):
        """Look up persistent learning memory for the current learner."""

        try:
            return lookup_user_memory(self.user_id)

        except Exception:
            logger.exception("Memory lookup failed")

            return {
                "success": False,
                "message": ("Memory is temporarily unavailable. Continue normally."),
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
        """Save useful learner information only after explicit consent."""

        facts: dict[str, object] = {}

        if learning_level:
            facts["learning_level"] = learning_level

        if current_topic:
            facts["current_topic"] = current_topic

        if topics_covered:
            facts["topics_covered"] = topics_covered

        try:
            result = save_user_memory(
                self.user_id,
                name,
                language_preference,
                facts,
            )

            return result

        except Exception:
            logger.exception("Memory save failed")

            return "Memory could not be saved. Do not claim that it was saved."

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
        """Fetch the next suitable learning exercise."""

        try:
            # If information is missing, try learner memory.
            if learning_level is None or current_topic is None:
                memory_result = lookup_user_memory(self.user_id)

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
                        learning_level = facts.get("learning_level")

                    if current_topic is None:
                        current_topic = facts.get("current_topic")

            # Defaults
            if not learning_level:
                learning_level = "beginner"

            if not current_topic:
                current_topic = "computer science"

            result = find_next_exercise(
                learning_level,
                current_topic,
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
            logger.exception("Exercise fetch failed")

            return {
                "success": False,
                "error": "tool_failure",
                "message": (
                    "I couldn't fetch a practice question right now. Let's try again."
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
        """

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
            logger.exception("Answer scoring failed")

            return {
                "success": False,
                "score": 0.0,
                "correct": False,
                "feedback": (
                    "I couldn't score that answer right now. Let's try again."
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
        """Return the learner's current score for this session."""

        try:
            result = format_session_score(self.user_id)

            return result

        except Exception:
            logger.exception("Score lookup failed")

            return {
                "success": False,
                "message": ("I couldn't calculate your score right now."),
            }

    # ========================================================
    # CREATE ESCALATION — DAY 7
    # ========================================================

    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        reason: str,
        summary: str,
        already_checked: str = "",
        urgency: str = "MEDIUM",
        language: str = "English",
        preferred_follow_up: str = "voice",
        learner_name: str | None = None,
    ):
        """
        Create a human teacher help request.

        Only call this tool AFTER the learner has given
        explicit consent to share their information.

        Parameters:
            reason: Why human help is needed
                    (e.g. "Frustrated Learner" or "Teacher Help")
            summary: Short summary of the learner's problem
            already_checked: What ShikshaMitra already tried
            urgency: LOW, MEDIUM, or HIGH
            language: Hindi, English, or Hinglish
            preferred_follow_up: voice, text, or dashboard
            learner_name: Name of learner if available
        """

        logger.info("[ESCALATION] Human help needed")
        logger.info("[ESCALATION] Reason: %s", reason)
        logger.info("[ESCALATION] Language detected: %s", language)
        logger.info("[ESCALATION] Consent requested")
        logger.info("[ESCALATION] Consent granted")
        logger.info("[ESCALATION] Creating request")

        try:
            result = create_escalation_record(
                learner_id=self.user_id,
                reason=reason,
                summary=summary,
                already_checked=already_checked,
                urgency=urgency,
                language=language,
                preferred_follow_up=preferred_follow_up,
                learner_name=learner_name,
            )

            if result.get("success"):
                if result.get("duplicate"):
                    logger.info("[ESCALATION] Duplicate found")
                    logger.info(
                        "[ESCALATION] Returning existing request %s",
                        result.get("reference_id"),
                    )
                else:
                    logger.info(
                        "[ESCALATION] Created %s",
                        result.get("reference_id"),
                    )
                    logger.info(
                        "[ESCALATION] Status: %s",
                        result.get("status"),
                    )
                    logger.info("[ESCALATION] Dashboard persistence successful")
            else:
                logger.warning("[ESCALATION] Failed to create request")

            return result

        except Exception:
            logger.exception("[ESCALATION] Escalation creation failed")
            return {
                "success": False,
                "message": (
                    "I couldn't create the teacher help "
                    "request right now. Let me try to "
                    "help you myself."
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
    initialize_escalation_table()
    initialize_call_analytics_table()

    # Auto-start dashboard server (port 8765) in background thread
    dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
    dashboard_thread.start()
    logger.info("Dashboard server thread launched on port 8765")

    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


# ============================================================
# AGENT SESSION
# ============================================================


@server.rtc_session(agent_name="my-agent")
async def my_agent(
    ctx: JobContext,
):

    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # --------------------------------------------------------
    # Read outbound call metadata
    # --------------------------------------------------------

    dial_info: dict = {}

    if ctx.job.metadata:
        try:
            dial_info = json.loads(ctx.job.metadata)
            if not isinstance(
                dial_info,
                dict,
            ):
                dial_info = {}
        except json.JSONDecodeError:
            logger.warning(
                "Invalid job metadata: %s",
                ctx.job.metadata,
            )

    is_outbound = dial_info.get("outbound", False) or bool(
        dial_info.get("phone_number")
    )

    if is_outbound:
        logger.info(
            "LOG Stage 1: Outbound call metadata detected (dial_info=%s)",
            dial_info,
        )

    # --------------------------------------------------------
    # Connect to LiveKit
    # --------------------------------------------------------

    await ctx.connect()

    # --------------------------------------------------------
    # Wait for Participant (Web or SIP)
    # --------------------------------------------------------

    try:
        participant = await ctx.wait_for_participant()
    except Exception as e:
        logger.warning(
            "LOG Outcome: No answer / Busy / Participant failed to join: %s",
            e,
        )
        ctx.shutdown()
        return

    learner_id = participant.identity
    call_id = ctx.room.name
    channel = (
        "sip"
        if (is_outbound or participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP)
        else "browser"
    )

    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        is_outbound = True
        logger.info(
            "LOG Stage 2: SIP Participant connected (Call Answered): %s",
            learner_id,
        )
    else:
        logger.info(
            "Inbound learner connected: %s",
            learner_id,
        )

    # Record call start in SQLite analytics
    start_call_record(call_id=call_id, learner_id=learner_id, channel=channel)

    # Disconnect listener for call outcome tracking
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        logger.info(
            "LOG Outcome: CALL DISCONNECTED - Participant %s left room",
            p.identity,
        )
        end_call_record(call_id)

    # --------------------------------------------------------
    # Start a fresh score for this call
    # --------------------------------------------------------

    start_score_session(learner_id)

    # --------------------------------------------------------
    # Load persistent memory
    # --------------------------------------------------------

    prior_memory = None

    try:
        memory_record = lookup_user_memory(learner_id)

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

            name = memory_record.get("name")

            language = memory_record.get("language_preference")

            level = facts.get("learning_level")

            topic = facts.get("current_topic")

            topics = facts.get("topics_covered")

            memory_lines = []

            if name:
                memory_lines.append(f"Learner name: {name}")

            if language:
                memory_lines.append(f"Preferred language: {language}")

            if level:
                memory_lines.append(f"Learning level: {level}")

            if topic:
                memory_lines.append(f"Current topic: {topic}")

            if (
                isinstance(
                    topics,
                    list,
                )
                and topics
            ):
                memory_lines.append(
                    "Topics covered: " + ", ".join(str(item) for item in topics)
                )

            if memory_lines:
                prior_memory = (
                    "The learner has previous "
                    "learning memory. Use it naturally "
                    "without exposing technical details.\n" + "\n".join(memory_lines)
                )

    except Exception:
        logger.exception("Failed to load learner memory")

    # --------------------------------------------------------
    # Create assistant
    # --------------------------------------------------------

    assistant = Assistant(
        user_id=learner_id,
        prior_memory=prior_memory,
        outbound_call=is_outbound,
        call_id=call_id,
    )

    # --------------------------------------------------------
    # Voice AI pipeline
    # --------------------------------------------------------

    logger.info(
        "LOG Stage 4: Starting AgentSession with Murf Falcon TTS, Deepgram STT, Gemini LLM"
    )

    session = AgentSession(
        # Speech-to-text (Nova-3 multilingual)
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
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
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
    # Debug Event Listeners for STT / Audio / Turn Lifecycle
    # --------------------------------------------------------

    @ctx.room.on("participant_connected")
    def _on_participant_connected(p: rtc.RemoteParticipant):
        logger.info(
            "LOG: Outbound participant joined: %s (kind=%s)",
            p.identity,
            p.kind,
        )

    @ctx.room.on("track_subscribed")
    def _on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ):
        logger.info(
            "LOG: Audio track subscribed for participant: %s (track_sid=%s, kind=%s)",
            participant.identity,
            track.sid,
            track.kind,
        )

    @session.on("user_state_changed")
    def _on_user_state_changed(ev):
        logger.info(
            "LOG: User state changed: %s -> %s",
            ev.old_state,
            ev.new_state,
        )
        if ev.new_state == "speaking":
            logger.info("LOG: User turn detected")

    @session.on("agent_state_changed")
    def _on_agent_state_changed(ev):
        logger.info(
            "LOG: Agent state changed: %s -> %s",
            ev.old_state,
            ev.new_state,
        )
        if ev.new_state == "thinking":
            logger.info("LOG: LLM response started")
        elif ev.new_state == "speaking":
            logger.info("LOG: TTS response started")

    @session.on("user_input_transcribed")
    def _on_user_input_transcribed(ev):
        if ev.is_final:
            logger.info(
                "LOG: STT final transcript: %s",
                ev.transcript,
            )
            logger.info(
                "USER TRANSCRIPT: %s",
                ev.transcript,
            )
        else:
            logger.info(
                "LOG: STT partial transcript: %s",
                ev.transcript,
            )

    @session.on("conversation_item_added")
    def _on_conversation_item_added(ev):
        logger.info(
            "LOG: Conversation item added (%s): %s",
            ev.item.role,
            ev.item.content,
        )

    # --------------------------------------------------------
    # Start session
    # --------------------------------------------------------

    await session.start(
        agent=assistant,
        room=ctx.room,
    )

    logger.info("LOG Stage 4: AgentSession started successfully")

    # --------------------------------------------------------
    # GREETING DISPATCH
    # --------------------------------------------------------

    if is_outbound:
        logger.info("LOG Stage 5: Greeting generation started (Outbound mode)")

        await session.generate_reply(
            instructions=(
                "Hello, this is ShikshaMitra AI. I'm calling to help you with your daily learning practice. "
                "You can ask me to stop future calls at any time. Is this a good time for a quick learning practice?"
            )
        )

        logger.info("LOG Stage 6: Outbound greeting completed")
        logger.info("LOG Stage 7: Waiting for learner response...")

    else:
        # Normal browser/inbound greeting
        await session.generate_reply(
            instructions=(
                "Greet the learner naturally. "
                "If returning memory exists, personalize the greeting. "
                "Otherwise introduce ShikshaMitra AI and ask what "
                "the learner would like to learn."
            )
        )

    logger.info(
        "ShikshaMitra AI session running for %s | outbound=%s",
        learner_id,
        is_outbound,
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    cli.run_app(server)
