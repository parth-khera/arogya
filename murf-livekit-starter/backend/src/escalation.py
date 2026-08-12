"""
Escalation notification via Discord webhook (free).

Set DISCORD_WEBHOOK_URL in backend/.env.local to enable.
If not set, escalations are saved to DB only — no notification sent.

Get a free webhook:
  Discord server → channel settings → Integrations → Webhooks → New Webhook → Copy URL
"""
import logging
import os

import aiohttp

logger = logging.getLogger("escalation")

URGENCY_COLOUR = {
    "emergency": 0xFF0000,  # red
    "high":      0xFF6600,  # orange
    "medium":    0xFFCC00,  # yellow
    "low":       0x00AA44,  # green
}


async def send_escalation_webhook(
    ref_id: str,
    caller_name: str | None,
    reason: str,
    summary: str,
    urgency: str,
) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        logger.info("DISCORD_WEBHOOK_URL not set — escalation %s saved to DB only", ref_id)
        return

    colour = URGENCY_COLOUR.get(urgency.lower(), 0x888888)
    name_str = caller_name or "Unknown caller"
    reason_label = reason.replace("_", " ").title()

    payload = {
        "embeds": [{
            "title": f"🚨 Aarogya Escalation — {ref_id}",
            "color": colour,
            "fields": [
                {"name": "Caller",   "value": name_str,    "inline": True},
                {"name": "Urgency",  "value": urgency.upper(), "inline": True},
                {"name": "Reason",   "value": reason_label, "inline": True},
                {"name": "Summary",  "value": summary[:500], "inline": False},
            ],
            "footer": {"text": "Aarogya Health Access · reply within 24h"},
        }]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status in (200, 204):
                    logger.info("Discord webhook sent for %s", ref_id)
                else:
                    logger.warning("Discord webhook returned %s for %s", resp.status, ref_id)
    except Exception as e:
        logger.warning("Discord webhook failed for %s: %s", ref_id, e)
