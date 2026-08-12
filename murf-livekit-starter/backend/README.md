# Backend — Aarogya Voice Health Agent

The Python backend for Aarogya. Runs a real-time voice AI pipeline using [LiveKit Agents](https://docs.livekit.io/agents), connecting Murf Falcon TTS, Deepgram STT, and Groq LLaMA into a conversational health access agent for India.

## How It Works

```
User speaks → [Deepgram STT] → text → [Groq LLaMA 3.3 70B] → response → [Murf Falcon TTS] → audio → User hears
```

LiveKit handles real-time audio transport. On red-flag symptoms or diagnosis requests, the agent asks for consent and creates a human escalation record visible at `http://localhost:8080`.

## Setup

### 1. Install dependencies

```bash
cd backend
uv venv --python 3.11
uv sync
uv run python src/agent.py download-files
```

### 2. Configure environment

```bash
cp .env.example .env.local
```

Fill in `.env.local`:

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | [cloud.livekit.io](https://cloud.livekit.io) → Settings |
| `LIVEKIT_API_KEY` | [cloud.livekit.io](https://cloud.livekit.io) → Settings |
| `LIVEKIT_API_SECRET` | [cloud.livekit.io](https://cloud.livekit.io) → Settings |
| `MURF_API_KEY` | [murf.ai/api/dashboard](https://murf.ai/api/dashboard) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `DISCORD_WEBHOOK_URL` | Optional — Discord channel → Integrations → Webhooks |

### 3. Run

```bash
# Agent (development, auto-reload)
uv run python src/agent.py dev

# Escalation dashboard (health worker view)
uv run python src/dashboard.py
# Open http://localhost:8080

# Console mode (no frontend needed)
uv run python src/agent.py console
```

## Project Structure

```
backend/
├── src/
│   ├── agent.py        # Agent pipeline, voice switching, all LLM-callable tools
│   ├── tools.py        # triage_symptoms(), find_health_facility()
│   ├── db.py           # SQLite: callers table + escalations table
│   ├── escalation.py   # Discord webhook for escalation notifications
│   ├── dashboard.py    # FastAPI dashboard — view/resolve escalations (port 8080)
│   └── outbound.py     # Outbound follow-up call dispatcher
├── data/               # SQLite DB (gitignored — contains caller data)
├── tests/
│   └── test_agent.py   # LLM-judged eval suite
├── .env.example
├── pyproject.toml
└── Dockerfile
```

## Tools

| Tool | Trigger | What it does |
|---|---|---|
| `triage_symptoms` | Any health complaint | Classifies RED / YELLOW / GREEN, returns spoken action |
| `find_health_facility` | "Where to go" questions | Queries data.gov.in live API, falls back to local index |
| `create_escalation` | RED triage or diagnosis request | Saves escalation to DB, fires Discord webhook, returns ref ID |
| `save_caller_info` | Name / condition learned | Persists caller profile to SQLite (consent required) |
| `forget_me` | Caller asks to be forgotten | Deletes all stored data for that caller |

## Escalation Flow

1. Agent detects red-flag symptom or diagnosis request
2. Asks caller for consent before sharing any information
3. If consent given — calls `create_escalation()` with: caller name, reason, summary, urgency, language, what the agent already checked
4. Record saved to `data/aarogya.db` (escalations table)
5. Discord embed sent (colour-coded by urgency) if `DISCORD_WEBHOOK_URL` is set
6. Caller receives reference ID — e.g. `ESC-3F9A2C`
7. Health worker opens `http://localhost:8080`, reviews the request, clicks Resolve

Duplicate open escalations for the same caller + reason are suppressed — the existing ref ID is returned instead.

## Voice Configuration

```python
VOICE_FEMALE = "Anisha"   # Indian English, female
VOICE_MALE   = "Arjun"    # Indian English, male
```

Gender is detected from the caller's name. Voice switches automatically mid-session.  
Browse all voices: [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library).

## Dashboard API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Open escalations (HTML) |
| `/resolved` | GET | Resolved escalations (HTML) |
| `/resolve/{ref_id}` | POST | Mark an escalation as resolved |
| `/api/escalations` | GET | All escalations as JSON (`?status=open\|resolved`) |
| `/api/escalations/{ref_id}` | GET | Single escalation detail as JSON |

## Testing

```bash
uv run pytest
```

Tests use LLM-as-judge evaluations to verify agent behaviour. Requires `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` as environment variables (or repo secrets for CI).

## Deployment

### Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/tIVCF1?referralCode=cNjn2P&utm_medium=integration&utm_source=template&utm_campaign=generic)

Set these environment variables in Railway:
- `MURF_API_KEY`, `DEEPGRAM_API_KEY`, `GROQ_API_KEY`
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- `DISCORD_WEBHOOK_URL` (optional)

### Docker

```bash
docker build -t aarogya-backend .
docker run --env-file .env.local aarogya-backend
```

## Links

- [Murf Falcon TTS Docs](https://murf.ai/api/docs/text-to-speech/streaming)
- [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library)
- [LiveKit Agents Docs](https://docs.livekit.io/agents)
- [Deepgram Nova-3 Docs](https://developers.deepgram.com)
- [Groq Console](https://console.groq.com)

## License

MIT — see [LICENSE](LICENSE).
