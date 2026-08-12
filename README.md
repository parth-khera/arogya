# 🏥 Aarogya — Voice AI Health Access Assistant for India

> **"Aarogya"** means *good health* in Sanskrit.  
> A voice agent that helps people in India navigate healthcare — in their own language, with an Indian voice.

[![Track](https://img.shields.io/badge/Track-Health%20Access-green)](https://github.com/parth-khera/arogya)
[![TTS](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api/docs)
[![STT](https://img.shields.io/badge/STT-Deepgram-blue)](https://deepgram.com)
[![LLM](https://img.shields.io/badge/LLM-Groq%20LLaMA-orange)](https://console.groq.com)
[![Transport](https://img.shields.io/badge/Transport-LiveKit-red)](https://livekit.io)
[![Challenge](https://img.shields.io/badge/10%20Days-VoiceForBharat-ff69b4)](https://discord.gg/FbKAy96Sz7)

---

## 🎯 Problem Statement

Millions of people in rural and semi-urban India struggle to:
- Know **when to see a doctor** vs. manage at home
- Find **nearby clinics or hospitals**
- Understand **government health schemes** like Ayushman Bharat
- Get health guidance in a **language and voice they trust**

Aarogya solves this with a **voice-first** health access assistant — no reading required, no app to install, just talk.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🎙️ Voice-first | Speak naturally, get spoken responses |
| 🇮🇳 Indian voice | Powered by Murf Falcon — Anisha (female) & Arjun (male) |
| 🧠 Gender-adaptive | Detects user's name and switches to matching Indian voice |
| 💊 Symptom triage | Classifies symptoms as RED / YELLOW / GREEN with next steps |
| 🏛️ Scheme awareness | Explains Ayushman Bharat and other govt health schemes |
| 🏥 Clinic finder | Finds nearby government hospitals, PHCs, and CHCs |
| 🧠 Caller memory | Remembers returning callers (with consent) across sessions |
| 🚨 Human escalation | Escalates red-flag symptoms to a health worker with consent |
| 📋 Escalation dashboard | Health workers see open requests and resolve them at `/` |
| ⚡ Ultra-low latency | Murf Falcon: 55ms model latency, 130ms time-to-first-audio |

---

## 🏗️ Architecture

```
🎙️ User speaks
      │
      ▼
 Deepgram STT  ──►  Groq LLaMA 3.3  ──►  Murf Falcon TTS
 (nova-3)           (70b-versatile)       (Anisha / Arjun)
      │                                         │
      └──────────── LiveKit ────────────────────┘
                  (real-time transport)
                        │
                        ▼
                  🔊 User hears

Escalation path (red-flag symptoms or diagnosis request):
  Agent asks consent → create_escalation() → SQLite DB + Discord webhook
                                                    │
                                                    ▼
                                         Health worker dashboard
                                         http://localhost:8080
```

---

## 🚨 Human Escalation (Day 7)

Aarogya knows when it cannot help alone. It escalates to a human health worker when:

1. **Red-flag symptom** — triage returns RED (chest pain, stroke, breathing difficulty, heavy bleeding, poisoning, severe burns, suicidal thoughts)
2. **Diagnosis request** — caller explicitly asks for a diagnosis or demands a medical opinion

### How it works

1. Agent detects the trigger and asks for consent in Hindi/English:  
   *"Kya main aapki yeh jaankari ek health worker ko bhej sakta hoon jo aapko callback kar sake?"*
2. If the caller agrees, `create_escalation()` is called — never without consent
3. A record is saved to SQLite with: caller name, reason, summary, urgency level, language, and what the agent already checked
4. A colour-coded Discord notification is sent (if `DISCORD_WEBHOOK_URL` is set)
5. The caller receives a reference ID:  
   *"Aapka reference number hai ESC-XXXXXX. Ek health worker 24 ghante mein aapko contact karenge."*
6. Health workers open `http://localhost:8080` to see open requests and mark them resolved

### Urgency levels

| Level | Colour | Examples |
|---|---|---|
| 🔴 Emergency | Red | Chest pain, stroke, unconscious |
| 🟠 High | Orange | Breathing difficulty, heavy bleeding |
| 🟡 Medium | Yellow | Persistent fever, pregnancy concern |
| 🟢 Low | Green | Diagnosis request, general concern |

### Deduplication

If the same caller already has an open escalation for the same reason, the existing reference ID is returned — no duplicate is created.

---

## 🚀 Quickstart

### Prerequisites

- Python 3.11
- Node.js 18+
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [pnpm](https://pnpm.io) — Node package manager

```bash
# Install uv (Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Install pnpm
npm install -g pnpm
```

### 1. Clone the repo

```bash
git clone https://github.com/parth-khera/arogya.git
cd arogya/murf-livekit-starter
```

### 2. Set up environment variables

```bash
cp backend/.env.example backend/.env.local
cp frontend/.env.example frontend/.env.local
```

Fill in these keys:

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | [cloud.livekit.io](https://cloud.livekit.io) |
| `LIVEKIT_API_KEY` | [cloud.livekit.io](https://cloud.livekit.io) |
| `LIVEKIT_API_SECRET` | [cloud.livekit.io](https://cloud.livekit.io) |
| `MURF_API_KEY` | [murf.ai/api/dashboard](https://murf.ai/api/dashboard) |
| `DEEPGRAM_API_KEY` | [deepgram.com](https://deepgram.com) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `DISCORD_WEBHOOK_URL` | Optional — Discord channel → Integrations → Webhooks |

### 3. Install dependencies

```bash
# Backend
cd backend
uv venv --python 3.11
uv sync
uv run python src/agent.py download-files

# Frontend
cd ../frontend
pnpm install
```

### 4. Run

Open 3 terminals:

```bash
# Terminal 1 — Backend agent
cd backend
uv run python src/agent.py dev

# Terminal 2 — Escalation dashboard (health worker view)
cd backend
uv run python src/dashboard.py

# Terminal 3 — Frontend
cd frontend
pnpm dev
```

- Voice agent: **http://localhost:3000**
- Escalation dashboard: **http://localhost:8080**

---

## 🗣️ Try These Conversations

**Normal call (no escalation):**
```
"Hi, my name is Priya. I have a mild cold and runny nose."
"What is Ayushman Bharat and am I eligible for it?"
"My child has had a fever for 3 days. Should I go to the hospital?"
"Where can I find a government hospital near me?"
"I have diabetes. What foods should I avoid?"
```

**Escalation call (triggers human help):**
```
"Hi, my name is Rahul. I have chest pain and difficulty breathing since morning."
→ Agent triages RED → asks consent → creates escalation → gives ref ID

"Can you tell me exactly what disease I have?"
→ Agent detects diagnosis request → asks consent → escalates
```

---

## 🎤 Voice Configuration

Aarogya automatically detects the user's gender from their name and switches voices:

| Gender | Voice | Language |
|---|---|---|
| Female | **Anisha** | Indian English |
| Male | **Arjun** | Indian English |

To change voices, edit `VOICE_FEMALE` and `VOICE_MALE` in `backend/src/agent.py`.  
Browse all Indian voices at [Murf Voice Library](https://murf.ai/api/docs/voices-styles/voice-library).

---

## 📁 Project Structure

```
arogya/
└── murf-livekit-starter/
    ├── backend/
    │   ├── src/
    │   │   ├── agent.py        # Agent logic, voice switching, system prompt, tools
    │   │   ├── tools.py        # triage_symptoms, find_health_facility
    │   │   ├── db.py           # SQLite: callers, escalations (never committed)
    │   │   ├── escalation.py   # Discord webhook notifications
    │   │   ├── dashboard.py    # Health worker escalation dashboard (port 8080)
    │   │   └── outbound.py     # Outbound follow-up call dispatcher
    │   ├── data/               # SQLite DB lives here (gitignored)
    │   ├── .env.example
    │   └── pyproject.toml
    └── frontend/
        ├── app/                # Next.js pages
        ├── components/         # UI components
        ├── app-config.ts       # Branding config
        └── .env.example
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Voice (TTS) | [Murf Falcon](https://murf.ai/api/docs) — fastest TTS, 55ms latency |
| Speech (STT) | [Deepgram](https://deepgram.com) nova-3 |
| Brain (LLM) | [Groq](https://console.groq.com) LLaMA 3.3 70B |
| Transport | [LiveKit](https://livekit.io) real-time audio |
| Backend | Python 3.11, livekit-agents |
| Database | SQLite (local, gitignored) |
| Notifications | Discord webhooks |
| Frontend | Next.js 15, TypeScript |

---

## 📅 Build Log — 10 Days of Voice Agents

| Day | What was built |
|---|---|
| Day 1 | Basic voice agent with Murf Falcon TTS + Deepgram STT + Groq LLaMA |
| Day 2 | Indian voice switching (Anisha / Arjun), gender detection from name |
| Day 3 | System prompt — health triage, scheme awareness, guardrails |
| Day 4 | Silence handling, Hinglish support, multilingual turn detection |
| Day 5 | `triage_symptoms` tool (RED/YELLOW/GREEN), `find_health_facility` tool |
| Day 6 | Caller memory with SQLite, consent gate, `save_caller_info`, `forget_me` |
| Day 7 | Human escalation — `create_escalation`, consent flow, Discord webhook, dashboard |

---

## 🌍 Part of VoiceForBharat

This project is built as part of **10 Days of Voice Agents — VoiceForBharat Edition**.

- Track: **Health Access**
- Challenge: Build voice agents that solve real problems for India
- Powered by: **Murf Falcon** — the fastest TTS API at 55ms latency

Follow the journey on [LinkedIn](https://linkedin.com/in/parth-khera) | [Discord](https://discord.gg/FbKAy96Sz7)

---

## 📄 License

MIT
