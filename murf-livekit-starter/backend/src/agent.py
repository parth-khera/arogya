import logging

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    inference,
    tokenize,
    room_io,
)
from livekit.plugins import murf, silero, groq, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO)

load_dotenv(".env.local")

VOICE_FEMALE = "Anisha"
VOICE_MALE = "Arjun"

MALE_NAMES = {
    "arjun", "rahul", "amit", "raj", "vijay", "suresh", "ramesh", "anil",
    "sanjay", "ajay", "rohit", "vikas", "deepak", "manoj", "ravi", "nikhil",
    "parth", "karan", "rohan", "aman", "akash", "harsh", "gaurav", "sachin",
    "vishal", "ankit", "sumit", "mohit", "kunal", "varun", "pranav", "dev",
    "aditya", "shubham", "tushar", "vivek", "naveen", "sandeep", "rakesh",
}

FEMALE_NAMES = {
    "priya", "anita", "sunita", "kavita", "pooja", "neha", "asha", "rekha",
    "sita", "geeta", "meena", "seema", "ritu", "nisha", "divya", "anjali",
    "shreya", "swati", "preeti", "komal", "pallavi", "madhuri", "deepa",
    "anisha", "sneha", "riya", "simran", "tanvi", "ishita", "aisha", "zara",
    "lakshmi", "saraswati", "durga", "radha", "meera", "usha", "lata",
}

SYSTEM_PROMPT = """You are Aarogya, a friendly health access assistant helping people in India navigate healthcare. Help users find nearby clinics, understand symptoms, know when to see a doctor, and learn about government health schemes like Ayushman Bharat. Speak in simple, clear Indian English. Be warm, patient, and never diagnose — always recommend consulting a doctor for medical decisions. Keep responses short and conversational, without formatting, emojis, or symbols.

At the very start of the conversation, greet the user and ask for their name."""


def make_tts(voice: str) -> murf.TTS:
    return murf.TTS(
        voice=voice,
        style="Conversation",
        tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
        text_pacing=True,
    )


def detect_gender(text: str) -> str | None:
    for word in text.lower().split():
        clean = word.strip(".,!?")
        if clean in MALE_NAMES:
            return "male"
        if clean in FEMALE_NAMES:
            return "female"
    return None


class Assistant(Agent):
    def __init__(self, session: AgentSession) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._session = session
        self._name_detected = False

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        await super().on_user_turn_completed(turn_ctx, new_message)
        text = new_message.text_content or ""
        logger.info("on_user_turn_completed fired, text=%r, name_detected=%s", text, self._name_detected)
        if not self._name_detected:
            gender = detect_gender(text)
            logger.info("detected gender=%s", gender)
            if gender == "male":
                self._name_detected = True
                self._session._tts = make_tts(VOICE_MALE)
                logger.info("Switched to male Indian voice: %s", VOICE_MALE)
            elif gender == "female":
                self._name_detected = True
                self._session._tts = make_tts(VOICE_FEMALE)
                logger.info("Switched to female Indian voice: %s", VOICE_FEMALE)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=make_tts(VOICE_FEMALE),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(session),
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

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
