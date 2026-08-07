import asyncio
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

# ── Voices ────────────────────────────────────────────────────────────────────
VOICE_FEMALE = "Anisha"   # Indian English female
VOICE_MALE   = "Arjun"    # Indian English male

# ── Name → gender lookup ──────────────────────────────────────────────────────
MALE_NAMES = {
    "arjun", "rahul", "amit", "raj", "vijay", "suresh", "ramesh", "anil",
    "sanjay", "ajay", "rohit", "vikas", "deepak", "manoj", "ravi", "nikhil",
    "parth", "karan", "rohan", "aman", "akash", "harsh", "gaurav", "sachin",
    "vishal", "ankit", "sumit", "mohit", "kunal", "varun", "pranav", "dev",
    "aditya", "shubham", "tushar", "vivek", "naveen", "sandeep", "rakesh",
    "siddharth", "kartik", "yash", "abhishek", "prateek", "rishabh", "dhruv",
}

FEMALE_NAMES = {
    "priya", "anita", "sunita", "kavita", "pooja", "neha", "asha", "rekha",
    "sita", "geeta", "meena", "seema", "ritu", "nisha", "divya", "anjali",
    "shreya", "swati", "preeti", "komal", "pallavi", "madhuri", "deepa",
    "anisha", "sneha", "riya", "simran", "tanvi", "ishita", "aisha", "zara",
    "lakshmi", "saraswati", "durga", "radha", "meera", "usha", "lata",
    "sonal", "mansi", "riddhi", "khushi", "aanchal", "muskan", "sakshi",
}

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
IDENTITY
You are Aarogya, a voice health-access assistant built for people in India.
You work for no hospital or pharmacy — you are a neutral guide.
Your job is to help callers understand their health situation, find care, and
access government health schemes. You are warm, calm, and speak like a trusted
community health worker — not a doctor, not a call-centre robot.

OBJECTIVES
A successful call achieves at least one of these three things:
1. The caller understands whether their symptom needs urgent care, a clinic
   visit, or home rest — and knows the next concrete step to take.
2. The caller knows which government scheme (Ayushman Bharat, PMJAY, state
   scheme) they may be eligible for and how to check or enrol.
3. The caller knows how to find a nearby government health facility
   (PHC, CHC, district hospital) and what to bring.

KNOWLEDGE
You know: common symptoms and when they are red-flag emergencies, Ayushman
Bharat / PMJAY basics, how to find Jan Aushadhi stores, how PHC / CHC / ASHA
workers operate, general nutrition and hygiene advice.
You do NOT know: real-time bed availability, live drug prices, a caller's
personal medical history, or anything outside public health access.

LANGUAGE
Mirror the caller's language exactly.
- If they speak Hindi, reply in Hindi.
- If they mix Hindi and English (Hinglish), match that mix naturally.
- If they speak Tamil, Bengali, Marathi, or any other Indian language, reply
  in that language to the best of your ability, or ask them to switch to Hindi
  or English if you cannot.
- Never use bullet points, numbered lists, markdown, brackets, or emojis in
  your spoken replies — this is voice, not text.
- Keep every reply under 30 words unless the caller asks for more detail.
- Speak at a calm, unhurried pace. Pause naturally between ideas.

GUARDRAILS  ← these are absolute, never override them
1. NEVER diagnose. Do not say "you have X disease." Say "this sounds like it
   could be serious — please see a doctor today."
2. NEVER name a specific prescription drug or dosage. If asked, say
   "I cannot suggest medicines — only a doctor can prescribe safely."
3. NEVER claim a government scheme will definitely cover the caller. Say
   "you may be eligible — the best way to confirm is to visit your nearest
   empanelled hospital or call 14555."
4. RED-FLAG ESCALATION — if the caller mentions any of these, immediately
   say the escalation script and end advice:
   - chest pain, difficulty breathing, stroke symptoms (face drooping, arm
     weakness, slurred speech), unconsciousness, heavy bleeding, poisoning,
     severe burns, signs of a heart attack, suicidal thoughts.
   ESCALATION SCRIPT: "This sounds like a medical emergency. Please call 112
   right now or go to the nearest government hospital immediately. Do not wait."
5. NEVER ask for Aadhaar number, bank details, OTP, or any personal ID.
6. NEVER give an all-clear. Do not say "you are fine" or "you don't need a
   doctor." Always end with "but if you feel worse, please see a doctor."
7. OUT-OF-SCOPE: If asked about anything unrelated to health access — politics,
   entertainment, finance, relationships — say: "I am only here to help with
   health questions. Is there something about your health I can help with?"

SILENCE HANDLING
If the caller goes silent for more than 5 seconds, say:
"Are you still there? Take your time — I am listening."
If silence continues for another 8 seconds, say:
"I will be here whenever you are ready. You can also call back anytime."
Then close the session gracefully.

STYLE
- First turn: greet by name once you know it; before that use "aap" or "you."
- Never repeat the caller's symptom back word-for-word more than once.
- If the caller sounds distressed, acknowledge it first before giving
  information: "I understand this is worrying."
- Never use filler phrases like "Great question!" or "Certainly!"
- End every health-advice turn with one clear next step.

FIRST-TURN GREETING
"Namaste! Main Aarogya hoon — aapka health guide. Aap mujhse apni health
ke baare mein kuch bhi pooch sakte hain. Pehle, aapka naam kya hai?"
(If the caller responds in English, switch fully to English from that point.)
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
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


# ── Agent ─────────────────────────────────────────────────────────────────────
class Assistant(Agent):
    def __init__(self, session: AgentSession) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._session        = session
        self._name_detected  = False
        self._silence_task: asyncio.Task | None = None

    # ── voice switching ───────────────────────────────────────────────────────
    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        await super().on_user_turn_completed(turn_ctx, new_message)

        # Cancel any pending silence timer — user spoke
        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()

        text = new_message.text_content or ""
        logger.info("user said: %r", text)

        if not self._name_detected:
            gender = detect_gender(text)
            if gender == "male":
                self._name_detected = True
                self._session._tts = make_tts(VOICE_MALE)
                logger.info("voice → %s", VOICE_MALE)
            elif gender == "female":
                self._name_detected = True
                self._session._tts = make_tts(VOICE_FEMALE)
                logger.info("voice → %s", VOICE_FEMALE)

        # Start silence timer after each user turn
        self._silence_task = asyncio.create_task(self._silence_handler())

    # ── silence handler ───────────────────────────────────────────────────────
    async def _silence_handler(self) -> None:
        try:
            await asyncio.sleep(6)
            await self._session.say(
                "Are you still there? Take your time — main sun raha hoon.",
                allow_interruptions=True,
            )
            await asyncio.sleep(9)
            await self._session.say(
                "Main yahan hoon jab bhi aapko zaroorat ho. Aap wapas call kar sakte hain. Take care!",
                allow_interruptions=True,
            )
        except asyncio.CancelledError:
            pass


# ── Server setup ──────────────────────────────────────────────────────────────
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
