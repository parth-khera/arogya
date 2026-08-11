"""
Aarogya outbound follow-up caller.

Use case: After a YELLOW/RED triage, Aarogya calls the person back the next day
to check if they got care and if they need further help.

Usage:
    # Dispatch calls for all callers with follow_up_needed=1
    uv run python src/outbound.py

    # Manually queue a follow-up for a specific user (for testing)
    uv run python src/outbound.py --queue <user_id>

    # Get a browser join link for a queued follow-up room
    uv run python src/outbound.py --link <user_id>

No SIP trunk or Twilio account required for browser-based demo.
For real phone calls: set LIVEKIT_SIP_TRUNK_ID + TWILIO_SIP_TRUNK_NUMBER in .env.local
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from livekit import api

sys.path.insert(0, str(Path(__file__).parent))
import db

load_dotenv(Path(__file__).parent.parent / ".env.local")

logger = logging.getLogger("outbound")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

LIVEKIT_URL        = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY    = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]
SIP_TRUNK_ID       = os.getenv("LIVEKIT_SIP_TRUNK_ID", "")


def make_token(room_name: str, identity: str) -> str:
    """Generate a LiveKit access token for a browser participant."""
    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(identity)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    return token.to_jwt()


async def dispatch_browser_call(user: dict) -> str:
    """
    Create a LiveKit room for the follow-up and print a browser join URL.
    The agent joins automatically; the user opens the link to answer.
    """
    user_id        = user["user_id"]
    name           = user.get("name") or "aap"
    triage_summary = user.get("last_triage") or "aapki pichhli call"
    room_name      = f"followup_{user_id}"

    lk = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )
    try:
        await lk.room.create_room(api.CreateRoomRequest(
            name=room_name,
            metadata=f"followup|{user_id}|{triage_summary}",
        ))
        token = make_token(room_name, name)
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        join_url = f"{frontend_url}?liveKitUrl={LIVEKIT_URL}&token={token}"
        logger.info("Follow-up room created: %s", room_name)
        print(f"\n{'='*60}")
        print(f"Follow-up call ready for: {name}")
        print(f"Room: {room_name}")
        print(f"Open this URL to answer the call:")
        print(f"  {join_url}")
        print(f"{'='*60}\n")
        return "dispatched"
    except Exception as e:
        logger.error("Failed to create room for %s: %s", user_id, e)
        return "failed"
    finally:
        await lk.aclose()


async def dispatch_sip_call(user: dict) -> str:
    """Place a real phone call via LiveKit SIP trunk (requires Twilio setup)."""
    phone          = user.get("phone")
    user_id        = user["user_id"]
    name           = user.get("name") or "aap"
    triage_summary = user.get("last_triage") or "aapki pichhli call"
    room_name      = f"followup_{user_id}"

    if not phone:
        logger.warning("No phone number for %s — skipping SIP call", user_id)
        return "skipped"

    lk = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )
    try:
        await lk.room.create_room(api.CreateRoomRequest(
            name=room_name,
            metadata=f"followup|{user_id}|{triage_summary}",
        ))
        await lk.sip.create_sip_participant(api.CreateSIPParticipantRequest(
            sip_trunk_id=SIP_TRUNK_ID,
            sip_call_to=phone,
            room_name=room_name,
            participant_identity=f"sip_{user_id}",
            participant_name=name,
            participant_metadata=f"followup|{user_id}|{triage_summary}",
        ))
        logger.info("SIP call dispatched to %s in room %s", phone, room_name)
        return "dispatched"
    except Exception as e:
        logger.error("SIP call failed for %s: %s", phone, e)
        return "failed"
    finally:
        await lk.aclose()


async def run_follow_ups(use_sip: bool = False) -> None:
    due = db.follow_up_due()
    if not due:
        logger.info("No follow-up calls due.")
        return
    logger.info("%d follow-up call(s) to dispatch", len(due))
    for user in due:
        if use_sip and SIP_TRUNK_ID:
            outcome = await dispatch_sip_call(user)
        else:
            outcome = await dispatch_browser_call(user)
        if outcome in ("dispatched", "skipped"):
            db.mark_followed_up(user["user_id"])
        await asyncio.sleep(1)


def queue_follow_up(user_id: str, phone: str | None = None) -> None:
    """Mark a caller as needing a follow-up (for testing)."""
    db.upsert_user(user_id=user_id, phone=phone, follow_up_needed=True)
    logger.info("Queued follow-up for %s", user_id)


async def print_link(user_id: str) -> None:
    """Print a browser join URL for an existing follow-up room."""
    record = db.get_user(user_id)
    name = (record or {}).get("name") or "caller"
    room_name = f"followup_{user_id}"
    token = make_token(room_name, name)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    print(f"{frontend_url}?liveKitUrl={LIVEKIT_URL}&token={token}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aarogya outbound follow-up dispatcher")
    parser.add_argument("--queue", metavar="USER_ID",
                        help="Queue a follow-up for this user_id")
    parser.add_argument("--phone", metavar="E164",
                        help="Phone number (optional, for SIP calls)")
    parser.add_argument("--link", metavar="USER_ID",
                        help="Print browser join URL for this user_id")
    parser.add_argument("--sip", action="store_true",
                        help="Use SIP trunk instead of browser room")
    args = parser.parse_args()

    if args.queue:
        queue_follow_up(args.queue, args.phone)
    elif args.link:
        asyncio.run(print_link(args.link))
    else:
        asyncio.run(run_follow_ups(use_sip=args.sip))
