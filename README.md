# VaakSetu 🌉

### Real-Time Dialect-Aware Voice AI with Multi-Signal Threat Detection for 1092 Helpline

> **PES IIT Bangalore Hackathon** • Theme 12: AI for 1092 Helpline • Prototype deadline: 7 May 2026

---

## What is VaakSetu?

**VaakSetu** (ವಾಕ್ ಸೇತು — "Voice Bridge") is a real-time voice-to-voice AI middleware for Karnataka's 1092 helpline. It bridges the gap between a citizen in crisis and the help they deserve.

### Core Innovation

> **Understanding must be verified, not assumed. Emergencies must be detected *before* understanding is complete.**

Unlike most voice AI tools that focus solely on transcription, VaakSetu runs **three parallel threat detection streams** simultaneously — keyword spotting, background noise analysis, and emotion detection — combined into a **Unified Threat Confidence Score (UTCS)** that can spike to CRITICAL *before* the NLP even finishes understanding the caller's intent.

**What makes this different from "just add Whisper + GPT":**
- 🎯 **Aho-Corasick keyword matching** across 200+ keywords in Kannada, Hindi, and English — including romanized Hindi (most systems miss "bachao bachao, maar raha hai")
- 🗣️ **4 Kannada dialect zones** (North KA, Coastal, Old Mysore, Hyderabad-KA) with zone-specific emergency vocabulary
- 🔇 **Silent Emergency detection** — even when the caller can't speak, background screaming/struggle/crying triggers CRITICAL
- ✅ **Verification Loop** — AI speaks back a summary in the caller's language and waits for confirmation before routing

---

## Quick Start

### Option 1: Docker (Recommended)
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key (optional — works without it)
docker-compose up --build
```
- **Backend:** http://localhost:8000
- **Dashboard:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs

### Option 2: Manual
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Option 3: Standalone Demo (Zero Dependencies)
Open `demo/standalone_demo.html` in any browser — no server needed, works offline.

---

## 3 Demo Scenarios

| # | Scenario | Language | UTCS | What Happens |
|---|----------|----------|------|--------------|
| 1 | **The Language Bridge** 🌉 | Kannada (dialect) | ~150 LOW | Citizen reports pothole in Kannada → transcribed → interpreted → summary spoken back in Kannada → citizen confirms |
| 2 | **Keyword Emergency** 🚨 | Hindi (code-mixed) | ~750 CRITICAL | "bachao bachao, wo mujhe maar raha hai!" → Tier-1 keywords instant-trigger → UTCS spikes → supervisor alerted → dashboard flashes red |
| 3 | **The Silent Emergency** 🤫 | English (minimal) | ~620 CRITICAL | Caller whispers "...help..." → noise analysis detects screaming/struggle → CRITICAL even without speech |

---

## Architecture

```
CITIZEN (1092 call)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  PARALLEL PROCESSING ENGINE                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Stream A  │  │ Stream B │  │   Stream C       │  │
│  │ ASR       │  │ Emotion  │  │   Noise Analysis │  │
│  │ (Whisper) │  │ (Librosa)│  │   (Spectral CNN) │  │
│  └─────┬─────┘  └─────┬────┘  └────────┬─────────┘  │
│        │              │               │              │
│        ▼              ▼               ▼              │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Keyword Engine (Aho-Corasick, 200+ KW, 3 lang) │ │
│  └──────────────────────┬──────────────────────────┘ │
│                         │                            │
│                         ▼                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │  UTCS Engine — Unified Threat Confidence Score   │ │
│  │  (Keywords×200 + Emotion×120 + Noise×150 + NLP) │ │
│  └──────────────────────┬──────────────────────────┘ │
│                         │                            │
│                         ▼                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │  NLP Engine (Claude API) — Intent + Summary      │ │
│  └──────────────────────┬──────────────────────────┘ │
│                         │                            │
│                         ▼                            │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Verification Loop — TTS → Citizen Confirms      │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
    │
    ▼
AGENT DASHBOARD (React + WebSocket)
```

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Backend** | FastAPI + Python 3.11 | REST API, WebSocket, pipeline orchestrator |
| **ASR** | OpenAI Whisper → SpeechRecognition (fallback) | Multilingual speech-to-text |
| **NLP** | Claude API (Anthropic) + Mock fallback | Intent extraction, summarization, dialect classification |
| **Keywords** | Aho-Corasick (ahocorasick-rs) | Sub-millisecond 200+ keyword matching across KN/HI/EN |
| **Emotion** | Librosa (pitch, RMS, ZCR, MFCC) | Panic/fear/distress/calm scoring from audio features |
| **Noise** | Spectral analysis (centroid, bandwidth) | Screaming/struggle/crying background detection |
| **TTS** | gTTS | Verification confirmation in Kannada/Hindi/English |
| **Frontend** | React + Vite | Operations dashboard with 6 pages |
| **Real-time** | WebSocket | Live broadcast to all connected agents |
| **Database** | SQLite (demo) / PostgreSQL (prod) | Calls, transcripts, verifications, feedback, events |
| **Telephony** | Twilio Voice API | Real phone number integration |
| **Docker** | Docker Compose | One-command deployment |

---

## Project Structure

```
VaakSetu/
├── backend/
│   ├── main.py              # FastAPI app, all routes, processing pipeline
│   ├── keywords.py          # Aho-Corasick keyword engine (KN/HI/EN)
│   ├── utcs.py              # Unified Threat Confidence Score engine
│   ├── asr.py               # Whisper + SpeechRecognition ASR
│   ├── nlp.py               # Claude API NLP engine
│   ├── emotion.py           # Librosa-based emotion detection
│   ├── noise.py             # Background noise analysis
│   ├── tts.py               # gTTS wrapper with caching
│   ├── verification.py      # Confirmation loop state machine
│   ├── database.py          # SQLite persistence layer
│   ├── learning.py          # Feedback ingestion pipeline
│   ├── websocket_manager.py # WebSocket broadcast
│   ├── twilio_handler.py    # Twilio voice webhook
│   ├── data/                # Keyword DBs, dialect maps, intent taxonomy
│   └── db/                  # Schema, models, seed data
├── frontend/src/
│   ├── pages/               # Dashboard, Demo, Operations, Analytics, AudioTest, Map, DB Viewer
│   ├── components/          # 14 modular UI components
│   └── hooks/               # WebSocket, call state, typing animation
├── demo/
│   └── standalone_demo.html # Zero-dependency offline demo
├── docker-compose.yml       # One-command deployment
├── Dockerfile.backend       # Python 3.11 + ffmpeg + Whisper
└── Dockerfile.frontend      # Node 20 + Vite dev server
```

---

## API Reference

| Method | Endpoint | Description |
|--------|---------|-------------|
| GET | `/health` | System health + engine status |
| POST | `/api/calls/start` | Start a new call session |
| POST | `/api/process` | **Main pipeline** — ASR→KW→NLP→Emotion→UTCS |
| POST | `/api/verify` | Citizen verification (yes/no/partial) |
| POST | `/api/calls/{id}/takeover` | Human takeover flag |
| POST | `/api/feedback` | Agent correction feedback |
| POST | `/api/demo/scenario/{id}` | Run demo scenario 1/2/3 |
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/db/tables` | Database viewer |
| WS | `/ws/dashboard` | Real-time WebSocket feed |

---

## Team

Built for **PES IIT Bangalore Hackathon 2026** — Theme 12: AI for 1092 Helpline.
