"""
Aarogya outbound follow-up caller.

Use case: After a YELLOW/RED triage, Aarogya calls the person back the next day
to check if they got care and if they need further help.

Usage:
    # Dispatch calls for all callers with follow_up_needed=1
    uv run python src/outbound.py

    # Manually queue a follow-up for a specific user (for testing)
    uv run python src/outbound.py --queue <user_id> --phone +91XXXXXXXXXX

Environment variables required (in .env.local):
    LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET
    TWILIO_SIP_TRUNK_NUMBER  — the number LiveKit SIP will call from
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from livekit import api

# make src/ importable when run directly
sys.path.insert(0, str(Path(__file__).parent))
import db

load_dotenv(Path(__file__).parent.parent / ".env.local")

logger = logging.getLogger("outbound")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LIVEKIT_URL        = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY    = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
SIP_TRUNK_NUMBER   = os.getenv("TWILIO_SIP_TRUNK_NUMBER", "")
SIP_TRUNK_ID       = os.getenv("LIVEKIT_SIP_TRUNK_ID", "")

# Outcome codes LiveKit SIP returns
_TERMINAL_OUTCOMES = {"answered", "no_answer", "busy", "failed", "voicemail"}


async def dispatch_call(user: dict) -> str:
    """
    Place one outbound SIP call for a user record.
    Returns the outcome string.
    """
    phone    = user["phone"]
    name     = user.get("name") or "aap"
    user_id  = user["user_id"]
    triage   = user.get("last_triage") or "aapki pichhli call"

    room_name = f"followup_{user_id}"

    lk = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    logger.info("Dispatching follow-up call → %s (%s)", phone, name)

    try:
        # Create a room for this outbound call
        await lk.room.create_room(api.CreateRoomRequest(name=room_name))

        # Dispatch the SIP participant (places the actual phone call)
        sip_req = api.CreateSIPParticipantRequest(
            sip_trunk_id=SIP_TRUNK_ID,
            sip_call_to=phone,
            room_name=room_name,
            participant_identity=f"sip_{user_id}",
            participant_name=name,
            # Pass follow-up context so the agent handler knows this is outbound
            participant_metadata=f"followup|{user_id}|{triage}",
        )
        await lk.sip.create_sip_participant(sip_req)
        logger.info("SIP participant created for %s in room %s", phone, room_name)
        return "dispatched"

    except Exception as e:
        logger.error("Failed to dispatch call to %s: %s", phone, e)
        return "failed"
    finally:
        await lk.aclose()


async def run_follow_ups() -> None:
    due = db.follow_up_due()
    if not due:
        logger.info("No follow-up calls due.")
        return

    logger.info("%d follow-up call(s) to dispatch", len(due))

    for user in due:
        outcome = await dispatch_call(user)
        if outcome == "dispatched":
            db.mark_followed_up(user["user_id"])
            logger.info("Marked %s as followed up", user["user_id"])
        else:
            logger.warning("Call failed for %s — will retry next run", user["user_id"])

        # Brief pause between calls to avoid SIP rate limits
        await asyncio.sleep(2)


def queue_follow_up(user_id: str, phone: str) -> None:
    """Manually mark a caller as needing a follow-up (for testing)."""
    db.upsert_user(user_id=user_id, phone=phone, follow_up_needed=True)
    logger.info("Queued follow-up for %s → %s", user_id, phone)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aarogya outbound follow-up dispatcher")
    parser.add_argument("--queue", metavar="USER_ID",
                        help="Queue a follow-up for this user_id (use with --phone)")
    parser.add_argument("--phone", metavar="E164_NUMBER",
                        help="Phone number in E.164 format, e.g. +919876543210")
    args = parser.parse_args()

    if args.queue:
        if not args.phone:
            parser.error("--phone is required with --queue")
        queue_follow_up(args.queue, args.phone)
    else:
        asyncio.run(run_follow_ups())
