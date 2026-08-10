"""
Day 5 tools for Aarogya.

Data sources:
- triage_symptoms: local curated dataset (always available, no network needed)
- find_health_facility: live query to data.gov.in open dataset API;
  falls back to a local index if the API is unreachable.
"""
import asyncio
import logging
from datetime import date

import aiohttp

logger = logging.getLogger("agent.tools")

# ── Triage dataset ─────────────────────────────────────────────────────────────
# Urgency levels: RED (emergency), YELLOW (clinic today), GREEN (home care)
# Each entry: list of trigger keywords → (level, spoken_action)
_TRIAGE_RULES: list[tuple[set[str], str, str]] = [
    # RED — call 112 immediately
    ({"chest", "pain", "heart", "attack", "cardiac"},
     "RED",
     "This could be a heart emergency. Please call 112 right now and do not wait."),
    ({"breath", "breathing", "breathe", "suffocating", "choke", "choking"},
     "RED",
     "Difficulty breathing is an emergency. Call 112 immediately."),
    ({"stroke", "face", "drooping", "arm", "weakness", "slurred", "speech"},
     "RED",
     "These are stroke warning signs. Call 112 right now — every minute matters."),
    ({"unconscious", "fainted", "collapse", "collapsed", "unresponsive"},
     "RED",
     "This is an emergency. Call 112 immediately."),
    ({"bleed", "bleeding", "blood", "heavy"},
     "RED",
     "Heavy bleeding needs emergency care. Call 112 or go to the nearest hospital now."),
    ({"poison", "poisoning", "overdose", "swallowed"},
     "RED",
     "This is a poisoning emergency. Call 112 immediately."),
    ({"suicid", "kill", "myself", "end", "life"},
     "RED",
     "Please call iCall right now at 9152987821 — they are available to help you."),
    ({"burn", "burns", "fire", "scalded"},
     "RED",
     "Severe burns need emergency care. Go to the nearest hospital immediately."),

    # YELLOW — see a doctor today or within 24 hours
    ({"fever", "temperature", "high", "days", "child", "infant", "baby"},
     "YELLOW",
     "A fever lasting more than two days, especially in a child, needs a doctor visit today. Go to your nearest PHC or government clinic."),
    ({"fever", "temperature"},
     "YELLOW",
     "If the fever is above 102°F or has lasted more than two days, please visit a clinic today."),
    ({"vomit", "vomiting", "diarrhea", "diarrhoea", "loose", "motions", "dehydrat"},
     "YELLOW",
     "Keep drinking ORS water. If vomiting or loose motions continue beyond a day, visit a clinic today."),
    ({"rash", "skin", "itching", "swelling", "allerg"},
     "YELLOW",
     "A spreading rash or swelling should be seen by a doctor today."),
    ({"headache", "severe", "worst", "sudden"},
     "YELLOW",
     "A sudden severe headache needs a doctor visit today — do not ignore it."),
    ({"pregnant", "pregnancy", "labour", "labor", "contractions"},
     "YELLOW",
     "Please go to your nearest government hospital or PHC with a maternity ward right away."),
    ({"diabetic", "diabetes", "sugar", "insulin"},
     "YELLOW",
     "For diabetes-related concerns, visit a doctor today. Do not adjust insulin on your own."),
    ({"blood", "pressure", "bp", "hypertension"},
     "YELLOW",
     "High blood pressure needs monitoring. Visit a PHC or clinic today to get it checked."),

    # GREEN — home care with monitoring
    ({"cold", "cough", "runny", "nose", "sneezing", "sore", "throat"},
     "GREEN",
     "This sounds like a common cold. Rest, drink warm fluids, and monitor for two days. See a doctor if it gets worse."),
    ({"headache", "mild", "stress", "tired"},
     "GREEN",
     "A mild headache can often be managed with rest and water. If it persists beyond a day, see a doctor."),
    ({"stomach", "ache", "gas", "acidity", "indigestion"},
     "GREEN",
     "Mild stomach discomfort can be managed with light food and rest. If pain is severe or lasts more than a day, visit a clinic."),
    ({"fatigue", "tired", "weakness", "weak"},
     "GREEN",
     "Rest and eat well. If weakness continues for more than three days, visit a PHC for a check-up."),
]

_RED_FLAG_SYMPTOMS = {
    "chest", "heart", "attack", "breath", "breathing", "stroke", "unconscious",
    "fainted", "collapse", "bleed", "bleeding", "poison", "overdose", "suicid",
    "burn", "burns",
}


def _classify(symptoms_text: str) -> tuple[str, str]:
    """Return (urgency_level, spoken_action) for a symptom description."""
    words = set(symptoms_text.lower().split())
    # Partial match for stemmed words
    expanded = set()
    for w in words:
        expanded.add(w)
        expanded.update(r for r in _RED_FLAG_SYMPTOMS if w.startswith(r[:4]))

    for keywords, level, action in _TRIAGE_RULES:
        if keywords & expanded:
            return level, action

    return "GREEN", (
        "I could not identify a specific concern from what you described. "
        "If you are worried, please visit your nearest PHC — it is always better to check."
    )


async def triage_symptoms(symptoms: str) -> dict:
    """
    Classify symptom severity and return urgency level + recommended action.
    Call this whenever a caller describes any physical symptom or health complaint.
    Data source: local curated triage rules (always available).
    Always mention that this is guidance only, not a diagnosis.
    """
    level, action = _classify(symptoms)
    logger.info("triage(%r) → %s", symptoms, level)
    return {
        "urgency": level,          # RED / YELLOW / GREEN
        "action": action,
        "data_note": "Triage guidance based on symptom keywords — not a medical diagnosis.",
        "as_of": str(date.today()),
    }


# ── Facility finder ────────────────────────────────────────────────────────────
# Live: data.gov.in open dataset — Health Infrastructure
# API endpoint returns PHC/CHC/district hospital records by state
_DATAGOV_URL = (
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    "?api-key=579b464db66ec23bdd000001cdd3946e44ce4aab825d0fb0f3e3f462"
    "&format=json&limit=5&filters[State_Name]={state}"
)

# Fallback local index — major government hospitals by state
_FALLBACK_FACILITIES: dict[str, list[dict]] = {
    "maharashtra": [
        {"name": "JJ Hospital Mumbai", "type": "Government Hospital", "phone": "022-23735555"},
        {"name": "KEM Hospital Mumbai", "type": "Government Hospital", "phone": "022-24107000"},
        {"name": "Sassoon General Hospital Pune", "type": "Government Hospital", "phone": "020-26128000"},
    ],
    "delhi": [
        {"name": "AIIMS New Delhi", "type": "Government Hospital", "phone": "011-26588500"},
        {"name": "Safdarjung Hospital", "type": "Government Hospital", "phone": "011-26707444"},
        {"name": "GTB Hospital", "type": "Government Hospital", "phone": "011-22582525"},
    ],
    "karnataka": [
        {"name": "Bowring & Lady Curzon Hospital Bengaluru", "type": "Government Hospital", "phone": "080-25561902"},
        {"name": "Victoria Hospital Bengaluru", "type": "Government Hospital", "phone": "080-26701150"},
    ],
    "tamil nadu": [
        {"name": "Rajiv Gandhi Government General Hospital Chennai", "type": "Government Hospital", "phone": "044-25305000"},
        {"name": "Stanley Medical College Hospital Chennai", "type": "Government Hospital", "phone": "044-25281349"},
    ],
    "uttar pradesh": [
        {"name": "SGPGI Lucknow", "type": "Government Hospital", "phone": "0522-2668700"},
        {"name": "Ram Manohar Lohia Hospital Lucknow", "type": "Government Hospital", "phone": "0522-2257540"},
    ],
    "west bengal": [
        {"name": "SSKM Hospital Kolkata", "type": "Government Hospital", "phone": "033-22041739"},
        {"name": "NRS Medical College Kolkata", "type": "Government Hospital", "phone": "033-22653041"},
    ],
    "gujarat": [
        {"name": "Civil Hospital Ahmedabad", "type": "Government Hospital", "phone": "079-22681111"},
        {"name": "SSG Hospital Vadodara", "type": "Government Hospital", "phone": "0265-2225000"},
    ],
    "rajasthan": [
        {"name": "SMS Hospital Jaipur", "type": "Government Hospital", "phone": "0141-2518888"},
        {"name": "JLN Hospital Ajmer", "type": "Government Hospital", "phone": "0145-2627100"},
    ],
    "telangana": [
        {"name": "Osmania General Hospital Hyderabad", "type": "Government Hospital", "phone": "040-24600177"},
        {"name": "Gandhi Hospital Hyderabad", "type": "Government Hospital", "phone": "040-27505566"},
    ],
    "madhya pradesh": [
        {"name": "Hamidia Hospital Bhopal", "type": "Government Hospital", "phone": "0755-2540222"},
        {"name": "MY Hospital Indore", "type": "Government Hospital", "phone": "0731-2527100"},
    ],
}

_GENERIC_FALLBACK = (
    "I could not find specific facility details right now. "
    "Please call the National Health Helpline at 1800-180-1104 — it is free — "
    "or visit nhp.gov.in to find your nearest government hospital."
)


async def find_health_facility(state: str, city: str | None = None) -> dict:
    """
    Find nearby government health facilities (PHC, CHC, district hospital) for a given
    state and optional city in India. Call this when a caller asks where to go for treatment,
    which hospital to visit, or how to find a government clinic near them.
    Always tell the caller when the data was fetched.
    """
    state_key = state.lower().strip()
    city_info = f" near {city}" if city else ""

    # Try live API first
    try:
        url = _DATAGOV_URL.format(state=state.title())
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    records = data.get("records", [])
                    if records:
                        facilities = [
                            {
                                "name": r.get("Facility_Name", "Unknown"),
                                "type": r.get("Facility_Type", "Government Facility"),
                                "district": r.get("District_Name", ""),
                            }
                            for r in records[:3]
                        ]
                        logger.info("facility lookup live: %s → %d results", state, len(facilities))
                        return {
                            "state": state,
                            "city": city,
                            "facilities": facilities,
                            "source": "data.gov.in (live)",
                            "as_of": str(date.today()),
                            "helpline": "1800-180-1104",
                        }
    except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
        logger.warning("facility API failed (%s), using fallback", e)

    # Fallback to local index
    for key, facilities in _FALLBACK_FACILITIES.items():
        if key in state_key or state_key in key:
            logger.info("facility lookup fallback: %s", key)
            return {
                "state": state,
                "city": city,
                "facilities": facilities,
                "source": "local index (network unavailable)",
                "as_of": "pre-loaded data",
                "helpline": "1800-180-1104",
            }

    # Nothing found
    return {
        "state": state,
        "city": city,
        "facilities": [],
        "source": "unavailable",
        "as_of": str(date.today()),
        "helpline": "1800-180-1104",
        "fallback_message": _GENERIC_FALLBACK,
    }
