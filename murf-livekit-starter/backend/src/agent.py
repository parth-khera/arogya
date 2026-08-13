import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

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
    room_io,
)
from livekit.plugins import murf, silero, groq, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

import db
from tools import triage_symptoms, find_health_facility
from escalation import send_escalation_webhook

logger = logging.getLogger("agent")
logging.basicConfig(level=logging.INFO)

load_dotenv(".env.local")

# ── Voices ────────────────────────────────────────────────────────────────────
VOICE_FEMALE = "Anisha"
VOICE_MALE   = "Arjun"

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

MEMORY & TOOLS
You have five tools:
- triage_symptoms(symptoms): call this EVERY TIME a caller describes any physical
  symptom or health complaint. Speak the action naturally — never read JSON.
  Always add: "but only a doctor can confirm this."
- find_health_facility(state, city): call this when a caller asks where to go,
  which hospital to visit, or how to find a clinic. Always say when the data is from.
  If facilities list is empty, read out the fallback_message and helpline number.
- create_escalation(...): call this when (1) triage returns RED urgency, or
  (2) the caller explicitly asks for a diagnosis or demands a doctor's opinion.
  ALWAYS ask permission first: "Kya main aapki yeh jaankari ek health worker
  ko bhej sakta hoon jo aapko callback kar sake?" — only escalate if they agree.
  After creating, give the caller their reference ID and say:
  "Aapka reference number hai [REF_ID]. Ek health worker 24 ghante mein
  aapko contact karenge."
- save_caller_info(...): call this when you learn something worth remembering
  (name, age band, ongoing condition, triage outcome). ALWAYS ask the caller
  for permission first: "Kya main aapki yeh jaankari yaad rakh sakta hoon
  agle baar ke liye?" — only save if they agree.
- forget_me(user_id): call this if the caller asks to be forgotten. Confirm
  deletion and never reference their data again.

ESCALATION TRIGGERS (call create_escalation when either is true)
1. RED urgency from triage_symptoms — chest pain, breathing difficulty, stroke,
   unconsciousness, heavy bleeding, poisoning, burns, suicidal thoughts.
2. Caller explicitly asks for a diagnosis, demands to know what disease they have,
   or insists the agent give a medical opinion.

ESCALATION CONSENT RULE
Never create an escalation without explicit verbal consent.
If the caller says no, do not call create_escalation.

TOOL FAILURE RULE
If any tool returns an error or empty data, say something useful out loud.
Never go silent. Never invent data. Say when the information is from.

CONSENT RULE (hard rule for Health Access)
Never save any health information without explicit verbal consent.
If the caller says no or is unsure, do not call save_caller_info.

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

LANGUAGE & SCRIPT
Mirror the caller's language exactly.
- If they speak Hindi, reply in Hindi using Devanagari script (नमस्ते), never romanized.
- If they mix Hindi and English (Hinglish), match that mix naturally.
- If they speak Tamil, Bengali, Marathi, or any other Indian language, reply
  in that language, or ask them to switch to Hindi or English if you cannot.
- Never use bullet points, numbered lists, markdown, brackets, or emojis in
  your spoken replies — this is voice, not text.
- Keep every reply under 30 words unless the caller asks for more detail.

GUARDRAILS  ← these are absolute, never override them
1. NEVER diagnose. Say "this sounds like it could be serious — please see a doctor today."
2. NEVER name a specific prescription drug or dosage.
3. NEVER claim a government scheme will definitely cover the caller.
4. RED-FLAG ESCALATION — chest pain, difficulty breathing, stroke symptoms,
   unconsciousness, heavy bleeding, poisoning, severe burns, suicidal thoughts:
   "This sounds like a medical emergency. Please call 112 right now or go to
   the nearest government hospital immediately. Do not wait."
5. NEVER ask for Aadhaar number, bank details, OTP, or any personal ID.
6. NEVER give an all-clear. Always end with "but if you feel worse, please see a doctor."
7. OUT-OF-SCOPE: "I am only here to help with health questions."

SILENCE HANDLING
If the caller goes silent for more than 5 seconds, say:
"Are you still there? Take your time — I am listening."
If silence continues for another 8 seconds, say:
"I will be here whenever you are ready. You can also call back anytime."
Then close the session gracefully.

STYLE
- First turn: greet by name once you know it; before that use "aap" or "you."
- Never repeat the caller's symptom back word-for-word more than once.
- If the caller sounds distressed, acknowledge it first.
- Never use filler phrases like "Great question!" or "Certainly!"
- End every health-advice turn with one clear next step.

FIRST-TURN GREETING
If the CALLER PROFILE block above shows a returning caller, greet them by name
and reference their last interaction naturally. Example:
"Namaste Priya! Pichhli baar aapne chest pain ke baare mein baat ki thi — kya ab theek hain?"
If CALLER PROFILE shows "New caller", use this greeting:
"Namaste! Main Aarogya hoon — aapka health guide. Aap mujhse apni health
ke baare mein kuch bhi pooch sakte hain. Pehle, aapka naam kya hai?"
"""


# ── Outbound system prompt ────────────────────────────────────────────────────
OUTBOUND_SYSTEM_PROMPT = """\
IDENTITY
You are Aarogya, a health-access assistant. You are making an outbound follow-up
call. The person did not initiate this call.

OPENING — say this FIRST, before anything else:
"Namaste, main Aarogya bol raha hoon — ek health assistant. Pichhli baar aapne
hum se {triage} ke baare mein baat ki thi. Main sirf yeh jaanna chahta tha ki
aap ab kaisa feel kar rahe hain. Agar aap baat nahi karna chahte, bas 'band karo'
keh dijiye aur main call khatam kar dunga."

RULES FOR OUTBOUND
- Keep the call under 3 minutes.
- If the person says stop, end, band karo, or hang up — say goodbye immediately
  and end the session.
- If they say they are fine — confirm, offer the helpline 1800-180-1104, say goodbye.
- If they describe a new or worsening symptom — triage it using triage_symptoms.
- Never ask for personal or financial information.
- End every call with: "Dhyan rakhiye. Aarogya helpline 1800-180-1104 pe hamesha
  available hai."

TOOLS
- triage_symptoms(symptoms): use if they describe any symptom.
- find_health_facility(state, city): use if they ask where to go.

GUARDRAILS
Same as inbound: no diagnosis, no drug names, 112 for emergencies.
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


def build_instructions(user_id: str) -> str:
    """Build system prompt with caller profile injected at the top."""
    record = db.get_user(user_id)
    if record:
        conditions = record.get("conditions") or []
        if isinstance(conditions, str):
            import json
            try:
                conditions = json.loads(conditions)
            except Exception:
                conditions = [conditions]
        profile = (
            f"CALLER PROFILE (returning caller)\n"
            f"Name: {record.get('name', 'unknown')}\n"
            f"Language preference: {record.get('language_pref', 'unknown')}\n"
            f"Age band: {record.get('age_band', 'unknown')}\n"
            f"Known conditions: {', '.join(conditions) if conditions else 'none'}\n"
            f"Last call summary: {record.get('last_triage', 'none')}\n"
        )
        logger.info("Returning caller loaded: %s", record.get("name"))
    else:
        profile = "CALLER PROFILE\nNew caller — no previous record.\n"
        logger.info("New caller: %s", user_id)
    return profile + "\n" + SYSTEM_PROMPT


# ── Agent ─────────────────────────────────────────────────────────────────────
class Assistant(Agent):
    def __init__(self, session: AgentSession, user_id: str) -> None:
        super().__init__(instructions=build_instructions(user_id))
        self._session       = session
        self._user_id       = user_id
        self._name_detected = False
        self._consent_given = False
        self._pending_save: dict = {}
        self._silence_task: asyncio.Task | None = None
        self._call_id       = str(uuid.uuid4())
        self._started_at    = datetime.now(timezone.utc).isoformat()
        # success flags — any one being True = successful call
        self._triage_given   = False
        self._scheme_given   = False
        self._facility_given = False
        self._escalated      = False

    # ── LLM-callable tools ────────────────────────────────────────────────────
    @function_tool()
    async def create_escalation(
        self,
        context: RunContext,
        reason: Annotated[str, "Why human help is needed: 'red_flag_symptom' or 'diagnosis_request'"],
        summary: Annotated[str, "Brief summary for the health worker — no passwords or IDs"],
        urgency: Annotated[str, "'emergency', 'high', 'medium', or 'low'"],
        language: Annotated[str, "Language the caller used, e.g. 'Hindi', 'English', 'Hinglish'"],
        agent_checked: Annotated[str, "What the agent already tried, e.g. 'triage_symptoms returned RED'"],
        caller_name: Annotated[str | None, "Caller's first name if known"] = None,
    ) -> dict:
        """Create a human-help escalation ONLY after the caller gives explicit verbal consent."""
        ref_id = db.create_escalation(
            user_id=self._user_id,
            caller_name=caller_name,
            reason=reason,
            summary=summary,
            urgency=urgency,
            language=language,
            agent_checked=agent_checked,
        )
        logger.info("escalation created: %s urgency=%s", ref_id, urgency)
        await send_escalation_webhook(ref_id, caller_name, reason, summary, urgency)
        self._escalated = True
        return {"ref_id": ref_id, "status": "open",
                "next_step": "A health worker will contact you within 24 hours."}

    @function_tool()
    async def triage_symptoms(
        self,
        context: RunContext,
        symptoms: Annotated[str, "The caller's symptom description in their own words"],
    ) -> dict:
        """Classify symptom urgency and get recommended action. Call this for ANY health complaint."""
        result = await triage_symptoms(symptoms)
        self._triage_given = True
        return result

    @function_tool()
    async def find_health_facility(
        self,
        context: RunContext,
        state: Annotated[str, "Indian state name, e.g. 'Maharashtra', 'Delhi', 'Karnataka'"],
        city: Annotated[str | None, "City or district name, optional"] = None,
    ) -> dict:
        """Find nearby government hospitals, PHCs, or CHCs for a given state/city in India."""
        result = await find_health_facility(state, city)
        self._facility_given = True
        return result

    @function_tool()
    async def save_caller_info(
        self,
        context: RunContext,
        user_id: Annotated[str, "The room name / caller ID"],
        name: Annotated[str | None, "Caller's first name"] = None,
        language_pref: Annotated[str | None, "Language they prefer (e.g. Hindi, English, Marathi)"] = None,
        age_band: Annotated[str | None, "Age range, e.g. '30-40', 'child', 'elderly'"] = None,
        conditions: Annotated[list[str] | None, "Ongoing health conditions mentioned, e.g. ['diabetes', 'hypertension']"] = None,
        last_triage: Annotated[str | None, "Brief outcome of this call, e.g. 'advised clinic visit for fever'"] = None,
    ) -> str:
        """Save or update caller information ONLY after receiving explicit verbal consent."""
        db.upsert_user(
            user_id=user_id,
            name=name,
            language_pref=language_pref,
            age_band=age_band,
            conditions=conditions,
            last_triage=last_triage,
        )
        self._consent_given = True
        logger.info("save_caller_info(%s) name=%s triage=%s", user_id, name, last_triage)
        return "Saved."

    @function_tool()
    async def forget_me(
        self,
        context: RunContext,
        user_id: Annotated[str, "The room name / caller ID to delete"],
    ) -> str:
        """Delete all stored information for this caller. Call only when they explicitly ask to be forgotten."""
        deleted = db.delete_user(user_id)
        logger.info("forget_me(%s) deleted=%s", user_id, deleted)
        return "Deleted." if deleted else "No record found."

    # ── voice switching ───────────────────────────────────────────────────────
    def _record_call_end(self, failure_type: str | None = None) -> None:
        ended_at = datetime.now(timezone.utc).isoformat()
        try:
            start = datetime.fromisoformat(self._started_at)
            end   = datetime.fromisoformat(ended_at)
            duration = int((end - start).total_seconds())
        except Exception:
            duration = 0
        success = self._triage_given or self._facility_given or self._escalated
        db.record_call(
            call_id=self._call_id,
            user_id=self._user_id,
            started_at=self._started_at,
            ended_at=ended_at,
            duration_sec=duration,
            outcome="success" if success else "failed",
            failure_type=None if success else (failure_type or "no_guidance_given"),
        )
        logger.info("call recorded: %s outcome=%s", self._call_id, "success" if success else "failed")

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        await super().on_user_turn_completed(turn_ctx, new_message)

        if self._silence_task and not self._silence_task.done():
            self._silence_task.cancel()

        text = new_message.text_content or ""
        logger.info("user said: %r", text)

        # Detect consent keywords and flush any pending save
        consent_words = {"haan", "han", "yes", "sure", "okay", "ok", "bilkul", "zaroor"}
        refusal_words = {"nahi", "nahin", "no", "nope", "mat", "band"}
        words = set(text.lower().split())
        if words & consent_words and self._pending_save:
            self._consent_given = True
            db.upsert_user(**self._pending_save)
            logger.info("Consent received — saved: %s", self._pending_save)
            self._pending_save = {}
        elif words & refusal_words:
            self._pending_save = {}
            logger.info("Consent refused — discarding pending save")

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

        # Stage name for saving (pending consent)
        if not self._consent_given:
            gender = detect_gender(text)
            if gender:
                for word in text.lower().split():
                    clean = word.strip(".,!?")
                    if clean in MALE_NAMES or clean in FEMALE_NAMES:
                        self._pending_save["user_id"] = self._user_id
                        self._pending_save["name"] = clean.capitalize()
                        break

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
            self._record_call_end(failure_type="user_silence_hangup")
        except asyncio.CancelledError:
            pass


# ── Outbound agent ────────────────────────────────────────────────────────────
class OutboundAssistant(Agent):
    """Agent for outbound follow-up calls placed via SIP."""
    def __init__(self, session: AgentSession, user_id: str, triage_summary: str) -> None:
        prompt = OUTBOUND_SYSTEM_PROMPT.replace("{triage}", triage_summary)
        super().__init__(instructions=prompt)
        self._session = session
        self._user_id = user_id

    @function_tool()
    async def triage_symptoms(
        self,
        context: RunContext,
        symptoms: Annotated[str, "The caller's symptom description"],
    ) -> dict:
        """Classify symptom urgency. Call for any health complaint."""
        return await triage_symptoms(symptoms)

    @function_tool()
    async def find_health_facility(
        self,
        context: RunContext,
        state: Annotated[str, "Indian state name"],
        city: Annotated[str | None, "City or district, optional"] = None,
    ) -> dict:
        """Find nearby government hospitals or PHCs."""
        return await find_health_facility(state, city)


# ── Server setup ──────────────────────────────────────────────────────────────
server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    await ctx.connect()

    # Detect outbound follow-up via participant metadata
    user_id = ctx.room.name
    triage_summary = None
    for p in ctx.room.remote_participants.values():
        meta = p.metadata or ""
        if meta.startswith("followup|"):
            parts = meta.split("|", 2)
            if len(parts) == 3:
                user_id, triage_summary = parts[1], parts[2]
            break

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=make_tts(VOICE_FEMALE),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    noise_fn = lambda params: (
        noise_cancellation.BVCTelephony()
        if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
        else noise_cancellation.BVC()
    )

    if triage_summary is not None:
        # Outbound follow-up call
        await session.start(
            agent=OutboundAssistant(session, user_id, triage_summary),
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(noise_cancellation=noise_fn),
            ),
        )
    else:
        # Inbound call
        assistant = Assistant(session, user_id)
        await session.start(
            agent=assistant,
            room=ctx.room,
            room_options=room_io.RoomOptions(
                audio_input=room_io.AudioInputOptions(noise_cancellation=noise_fn),
            ),
        )
        try:
            await session.wait_for_disconnect()
        finally:
            assistant._record_call_end()


if __name__ == "__main__":
    cli.run_app(server)
