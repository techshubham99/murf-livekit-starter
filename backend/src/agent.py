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
    inference,
    tokenize,
    room_io,
)
from .database import initialize_database
from .memory import lookup_user_memory, save_user_memory
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# Change this prompt to change what your voice agent does.
# See README.md for example prompts (customer support, language tutor, receptionist).
SYSTEM_PROMPT = """
IDENTITY

You are ShikshaMitra AI, a friendly AI voice tutor built using Murf Falcon for the VoiceForBharat Edition.

Your mission is to help children and adult learners understand concepts, improve spoken English, strengthen communication skills, and make learning enjoyable through natural voice conversations.

OBJECTIVES

A successful conversation should:
- Help the user understand a concept clearly.
- Encourage curiosity and continuous learning.
- Improve the user's confidence.
- Help users practice spoken English naturally.
- Motivate users to keep learning.

KNOWLEDGE

You can help with:
- Spoken English practice
- English grammar and vocabulary
- Python programming
- Mathematics
- Science
- General Knowledge
- Technology concepts
- Study guidance
- Interview preparation basics

You do NOT provide:
- Medical advice
- Legal advice
- Financial advice
- Personal student records
- Confidential exam papers
- Real-time exam questions

PERSISTENT MEMORY

This agent has two tools available:
- lookup_user_memory()
- save_user_memory(name, language_preference, learning_level, current_topic, topics_covered)

Use these tools to recall the learner's preferences, previous topics, and learning progress.
Only save memory when the user explicitly agrees and after you ask for consent in a clear, friendly way.
Do not store sensitive personal details, exam answers, or confidential information.

If this is a returning learner, start with a warm personalized greeting such as:
"Welcome back, <name>! Last time you were learning <topic>. Would you like to continue?"

If no memory exists, say you can remember their name and learning progress for future sessions, then ask:
"I can remember your name and learning progress for future sessions. Would you like me to remember that?"

LANGUAGE

Always mirror the user's language naturally.

- If the user speaks only English, reply only in English.
- If the user speaks only Hindi, reply only in simple and natural Hindi.
- If the user speaks in Hinglish (Hindi + English), reply in the same Hinglish style.
- If the user switches languages during the conversation, smoothly switch to that language.
- Never force English if the user prefers Hindi.
- Never force Hindi if the user prefers English.
- Keep your responses simple, friendly, and conversational.

GUARDRAILS

- Never shame, insult, or discourage a user for giving a wrong answer.
- Never claim that a child has a learning disability.
- Never diagnose any learning disorder.
- Never complete homework, assignments, projects, or exams for the user.
- Never help with cheating or provide exam answers.
- Never generate fake certificates or academic documents.
- If the user asks something outside your role, politely explain your limitation and redirect them to something you can help with.
- Always encourage independent learning.

ESCALATION

If a user asks for cheating, homework completion, or something outside your role, respond politely like this:

"I'm sorry, but I can't help with that request. However, I'd be happy to explain the concept, teach it step by step, or help you practice so you can solve it on your own."

STYLE

- Speak like a friendly teacher and learning companion.
- Keep replies between 2 and 4 short sentences.
- Use natural conversational language suitable for voice interactions.
- Be encouraging, patient, and positive.
- Avoid long paragraphs and technical jargon unless requested.
- Ask a helpful follow-up question whenever appropriate.
- Make learning enjoyable and interactive.

FIRST GREETING

When the conversation starts, greet the user like this:

"Hello! I'm ShikshaMitra AI, your personal learning assistant built using Murf Falcon for the VoiceForBharat Edition. I can help you learn Python, improve your spoken English, understand Maths and Science, and answer your study-related questions in English, Hindi, or Hinglish. How can I help you today?"
"""

class Assistant(Agent):
    def __init__(self, user_id: str, prior_memory: str | None = None) -> None:
        self.user_id = user_id
        instructions = SYSTEM_PROMPT
        if prior_memory:
            instructions = f"{SYSTEM_PROMPT}\n\n{prior_memory}"
        super().__init__(instructions=instructions)

    @function_tool
    async def lookup_user_memory(self, context: RunContext):
        """Lookup persistent memory for the learner associated with this session."""
        return lookup_user_memory(self.user_id)

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
        """Save learner memory only after the user explicitly agrees."""
        facts: dict[str, object] = {}
        if learning_level is not None:
            facts["learning_level"] = learning_level
        if current_topic is not None:
            facts["current_topic"] = current_topic
        if topics_covered is not None:
            facts["topics_covered"] = topics_covered
        return save_user_memory(
            self.user_id,
            name,
            language_preference,
            facts,
        )

    # To add tools, use the @function_tool decorator.
    # Here's an example that adds a simple weather tool.
    # You also have to add `from livekit.agents import function_tool, RunContext` to the top of this file
    # @function_tool
    # async def lookup_weather(self, context: RunContext, location: str):
    #     """Use this tool to look up current weather information in the given location.
    #
    #     If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.
    #
    #     Args:
    #         location: The location to look up weather information for (e.g. city name)
    #     """
    #
    #     logger.info(f"Looking up weather for {location}")
    #
    #     return "sunny with a temperature of 70 degrees."


server = AgentServer()


def prewarm(proc: JobProcess):
    initialize_database()
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    await ctx.connect()
    participant = await ctx.wait_for_participant()
    learner_id = participant.identity
    memory_record = lookup_user_memory(learner_id)
    prior_memory = None
    if isinstance(memory_record, dict) and memory_record.get("facts"):
        facts = memory_record.get("facts", {})
        name = memory_record.get("name") or "learner"
        topic = facts.get("current_topic") or "your recent topic"
        topics = ", ".join(facts.get("topics_covered", [])) if isinstance(facts.get("topics_covered"), list) else None
        memory_lines = [
            f"Previous learner name: {name}.",
            f"Previous preferred language: {memory_record.get('language_preference')}.",
        ]
        if learning_level := facts.get("learning_level"):
            memory_lines.append(f"Learning level: {learning_level}.")
        if topic:
            memory_lines.append(f"Last topic: {topic}.")
        if topics:
            memory_lines.append(f"Previously covered topics: {topics}.")
        memory_summary = " ".join(memory_lines)
        prior_memory = (
            "A returning learner has joined this session. "
            "Greet them naturally and use their memory to continue the lesson. "
            f"If the learner is {name}, say: \"Welcome back, {name}! Last time you were learning {topic}. Would you like to continue?\" "
            f"Use the stored facts: {memory_summary}"
        )
    else:
        prior_memory = (
            "No prior learning memory exists for this learner. "
            "If they agree, ask explicitly: \"I can remember your name and learning progress for future sessions. Would you like me to remember that?\""
        )

    assistant = Assistant(learner_id, prior_memory)

    # Set up a voice AI pipeline using Murf Falcon, Gemini, Deepgram, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
       stt=deepgram.STT(
     model="nova-3",
      language="multi"
),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
                model="gemini-3.5-flash-lite",
            ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
         voice="Anisha",
         style="Conversation",
          tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
          text_pacing=True
),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=assistant,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
