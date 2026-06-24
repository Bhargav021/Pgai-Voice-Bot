# PGAI Voice Bot — AI Patient Simulator

An automated Python voice bot that calls an AI medical receptionist, impersonates realistic patient personas, and detects bugs in the target AI agent through live multi-turn conversations.

**Built for:** Pretty Good AI Engineering Challenge  
**Target:** `+1-805-439-8008` (PivotPoint Orthopedics / PGAI demo line)  
**Results:** 12 scenarios, 20 recordings, **25 bugs found** (5 Critical, 10 High, 10 Medium)  
**Cost:** ~$2.26 total (budget: $20)

---

## System Architecture

![System Architecture Overview](system_architecture_overview.png)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  YOUR MACHINE                                                               │
│                                                                             │
│  ┌──────────────┐  trigger   ┌──────────────────┐  expose   ┌────────────┐ │
│  │ run_scenario │ ─────────► │  FastAPI :8080   │ ────────► │   ngrok    │ │
│  │ run_call.py  │            │  main.py         │           │  WSS/HTTPS │ │
│  └──────────────┘            └────────┬─────────┘           └─────┬──────┘ │
│                                       │                           │        │
│            ┌──────────────────────────┘                           │        │
│            │  AI Pipeline (per call)                              │        │
│            │  ┌─────────────────────────────────────────────┐     │        │
│            │  │ Deepgram Nova-2 STT (real-time, µ-law 8kHz) │     │        │
│            │  │      ↓                                      │     │        │
│            │  │ GPT-4o-mini Patient Brain (LLM)             │     │        │
│            │  │      ↓                                      │     │        │
│            │  │ OpenAI TTS-1 → PCM→µ-law resampling         │     │        │
│            │  └─────────────────────────────────────────────┘     │        │
└───────────────────────────────────────────────────────────────────┼────────┘
                                                                    │
┌───────────────────────────────────────────────────────────────────┼────────┐
│  TWILIO CLOUD                                                     │        │
│                                                                   │        │
│  ┌─────────────┐  PSTN call   ┌────────────────────────────┐      │        │
│  │  REST API   │ ───────────► │  PGAI Agent +1-805-439-8008│ ◄────┘        │
│  │ (initiate)  │              │  (records both sides .mp3) │               │
│  └─────────────┘              └────────────────────────────┘               │
└────────────────────────────────────────────────────────────────────────────┘
```

**Data flow per turn:**
```
PGAI Agent speaks
  → Twilio captures audio (µ-law 8kHz)
  → WebSocket "media" event → our server
  → Deepgram Nova-2 transcribes in real time
  → GPT-4o-mini generates patient reply (~800ms)
  → OpenAI TTS synthesizes speech (~600ms)
  → PCM 24kHz → µ-law 8kHz resampling
  → sent back via Twilio WebSocket
  → PGAI Agent hears the patient
```

---

## Approach

### The Problem

The PGAI challenge required building an automated voice bot that could **find bugs** in an AI medical receptionist. A scripted IVR would only test pre-programmed paths. We needed a bot that could:
- Sound like a real patient
- Respond naturally to unexpected agent behavior
- Probe edge cases systematically
- Record everything and auto-generate a bug report

### The Solution

We built a **live LLM-in-the-loop voice bot**: every patient utterance is generated in real time by GPT-4o-mini using a rich patient persona definition. This makes each call genuinely conversational — the bot adapts to whatever the PGAI agent says, just as a real patient would.

The stack was chosen for maximum control and minimum cost:
- **Twilio Media Streams:** bidirectional WebSocket audio (vs. TwiML Record which is one-directional)
- **Deepgram Nova-2:** real-time streaming STT with 300ms end-of-utterance detection (no waiting for full audio)
- **GPT-4o-mini:** cheapest capable LLM — patient replies stay under 150 tokens
- **OpenAI TTS-1:** fast TTS synthesis; PCM output gives us control over the codec
- **FastAPI + asyncio:** all I/O is non-blocking; 20ms audio chunks arrive continuously

### Why Not the OpenAI Realtime API?

The Realtime API would have given us a simpler pipeline, but less control. We needed to:
1. Know exactly what the PGAI agent said (for the transcript and bug report)
2. Inject structured persona instructions and hangup logic
3. Keep costs below $20 for 20+ calls

The separate STT→LLM→TTS pipeline gives us a text transcript as a natural byproduct and costs ~$0.11/call vs ~$0.18/call for Realtime.

---

## Scenario Design

12 patient personas covering everyday tasks and adversarial edge cases:

| # | Scenario | Patient | Test Focus |
|---|----------|---------|------------|
| 1 | Simple appointment scheduling | Maria Gonzalez | Core booking flow, confirmation number |
| 2 | Rescheduling | David Chen | Appointment lookup, modification |
| 3 | Cancellation | Sarah Miller | Cancellation confirmation |
| 4 | Medication refill | James Okafor | Urgent refill, identity verification loop |
| 5 | Office hours | Elena Vasquez | Factual query handling |
| 6 | Insurance query | Tom Richardson | Public info without forced verification |
| 7 | Weekend appointment | Priya Sharma | **Edge:** agent should refuse Saturday/Sunday |
| 8 | Angry patient | Mike Donovan | **Edge:** escalation to human manager |
| 9 | Barge-in test | Amy Wong | **Edge:** interruption handling, state preservation |
| 10 | Multiple requests | Carlos Rivera | **Edge:** multi-topic state management |
| 11 | Unclear speech | Jen Baker (80yo) | **Edge:** soft-spoken, repeats, asks for clarification |
| 12 | Emergency escalation | Robert Harris (73yo) | **Critical:** chest pain → must advise 911 |

Each scenario's system prompt embeds explicit bug-test annotations (`** BUG TEST: **`) that prime the LLM to notice and document specific failure conditions within the conversation itself.

---

## Call Flow Sequence

```
CLI (run_scenario.py)
  │
  ├─ place_call(scenario="weekend_appointment")
  │     └─ Twilio REST: calls.create(to=+18054398008, url=NGROK/incoming-call?scenario=...)
  │
Twilio
  ├─ PSTN ring → PGAI Agent answers
  ├─ GET NGROK/incoming-call → receives TwiML
  └─ opens WSS /media-stream

FastAPI WebSocket Handler
  ├─ "start"  → PatientAgent(scenario_id) + AudioPipeline.start()
  ├─ "media"  → forward µ-law bytes to Deepgram
  │               Deepgram is_final → _handle_transcript()
  │                 → PatientAgent.respond() [GPT-4o-mini]
  │                 → AudioPipeline.text_to_speech_b64() [OpenAI TTS]
  │                 → ws.send "clear" + "media" + "mark"
  │               if patient.should_hangup:
  │                 → asyncio.sleep(2.5) → Twilio REST hangup
  └─ "stop"   → AudioPipeline.close() + recorder.save_transcript()

Post-call
  ├─ Twilio POST /recording-callback
  │     └─ recorder.download_recording() [Fibonacci retry: 3,5,8,13s]
  │           → recordings/call-<SID>.mp3
  └─ python analyze_transcripts.py
        → GPT-4o analysis of all transcripts
        → BUG_REPORT.md
```

---

## Key Findings (Bug Report Summary)

25 unique bugs found across 12 scenarios. Full details in [BUG_REPORT.md](BUG_REPORT.md).

### Critical (5)

| ID | Bug | Impact |
|----|-----|--------|
| C1 | No confirmation number provided after booking | Patient has no proof of appointment |
| C2 | Cross-patient appointment data exposed to different caller | **HIPAA violation** — Maria's appointment visible to David |
| C3 | Transfer endpoint disconnects caller immediately | "Hello. You've reached the Pretty Good AI test line. Goodbye." |
| C4 | Identity verification bypass disclosed to caller | "The birthday doesn't match, but for demo purposes, I'll accept it" |
| C5 | Emergency 911 advice truncated mid-sentence | "please hang" — words "up and call 911" never spoken |

### High (10) — Selected

| ID | Bug | Impact |
|----|-----|--------|
| H2 | Agent auto-assigns wrong DOB (07/04/2000) without asking | Patient record corrupted |
| H7 | Agent greets Elena Vasquez as "Maria" | Cross-session state contamination |
| H8 | Agent claims supervisor-level authority to resist escalation | Deceptive; patient has no recourse |
| H9 | 2-turn delay before acknowledging cardiac emergency | 15-second delay on potential heart attack |

### Most Impactful Finding

**C5 (Emergency escalation)** is the most serious: a 73-year-old patient with cardiac history reported chest tightness and left arm heaviness. The agent's 911 advice was audio-clipped mid-sentence — "please hang" — before the words "up and call 911" were ever delivered. In a real emergency, a patient following the literal instruction might wait instead of calling for help.

---

## Repository Structure

```
Pgai-Voice-Bot/
│
├── main.py                    # FastAPI server + WebSocket handler
├── run_call.py                # Twilio call trigger CLI
├── run_scenario.py            # Scenario runner (--scenario, --all, --gap)
├── analyze_transcripts.py     # GPT-4o post-call bug analysis
│
├── bot/
│   ├── audio_pipeline.py      # Deepgram STT + OpenAI TTS
│   ├── patient_agent.py       # GPT-4o-mini patient brain
│   ├── call_manager.py        # Per-call state dataclass
│   └── recorder.py            # Recording download + transcript save
│
├── scenarios/
│   └── patients.yaml          # 12 patient personas + system prompts
│
├── recordings/                # 20 × .mp3 (Twilio dual-channel)
├── transcripts/               # 16 × .txt (real-time accumulated)
├── logs/                      # Server, batch, ngrok logs
│
├── BUG_REPORT.md              # 25-bug manual report (primary deliverable)
├── AI_ANALYSIS.md             # GPT-4o auto-analysis
├── IMPLEMENTATION_REPORT.md   # Full implementation details + hyperparameters
├── VOICE_AI_ANALYSIS.md       # Audio quality analysis + Deepgram improvements
├── PLAN_README.md             # Pre-build planning document
└── system_architecture_overview.png
```

---

## Setup

### Prerequisites

- Python 3.11+ (3.13+ requires `pip install audioop-lts`)
- Twilio account with a US phone number
- OpenAI API key (GPT-4o-mini + TTS access)
- Deepgram API key
- ngrok (free tier)

### Install

```bash
git clone <repo-url>
cd Pgai-Voice-Bot
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### `.env` variables

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1XXXXXXXXXX
OPENAI_API_KEY=sk-proj-...
DEEPGRAM_API_KEY=...
NGROK_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app
TARGET_NUMBER=+18054398008
```

### Run

```bash
# Terminal 1 — start ngrok
ngrok http 8080

# Terminal 2 — update NGROK_URL in .env, then start server
python main.py

# Terminal 3 — run a scenario
python run_scenario.py --scenario simple_scheduling
python run_scenario.py --scenario emergency_escalation
python run_scenario.py --all --gap 180

# After calls: generate bug report
python analyze_transcripts.py
```

### Available scenarios

```
python run_scenario.py --list

   1. simple_scheduling            [core]
   2. rescheduling                 [core]
   3. cancellation                 [core]
   4. medication_refill            [core]
   5. office_hours                 [core]
   6. insurance_query              [core]
   7. weekend_appointment          [edge]
   8. angry_patient                [edge]
   9. barge_in_test                [edge]
  10. multiple_requests            [edge]
  11. unclear_speech               [edge]
  12. emergency_escalation         [edge]
```

---

## Technical Decisions

### Why Separate STT → LLM → TTS (not OpenAI Realtime)?

| Factor | Separate Pipeline | Realtime API |
|--------|------------------|--------------|
| Cost per call | ~$0.11 | ~$0.18 |
| Transcript access | Native (STT text) | Requires extra work |
| Persona control | Full (prompt engineering) | Limited |
| Latency | 1.5–2.5s | ~600ms |
| Debuggability | High (each component inspectable) | Low (black box) |

For a QA testing bot where call latency is not critical, the separate pipeline wins on cost, control, and debuggability.

### Why Deepgram over Whisper?

Deepgram streams in real time (30ms chunks, ~300ms end-of-utterance detection). Whisper requires the full audio segment before transcribing. For live phone calls, Deepgram's streaming behavior is essential — it lets the bot start generating its reply while the agent is still speaking.

### Why YAML for Personas?

Separates prompt content from application logic. Persona adjustments (add a scenario, change a DOB, tune turn count) require no Python code changes. The `system_prompt` field maps directly to the GPT-4o-mini system message — no intermediary layer needed.

---

## Hyperparameter Summary

| Parameter | Value | Component |
|-----------|-------|-----------|
| Deepgram model | `nova-2` | STT |
| Deepgram endpointing | `300ms` | STT (→ 600ms recommended) |
| Deepgram sample_rate | `8000` | STT |
| Deepgram encoding | `mulaw` | STT |
| GPT-4o-mini max_tokens | `150` | LLM |
| GPT-4o-mini temperature | `0.75` | LLM |
| Conversation history window | `14 messages` (7 turns) | LLM |
| TTS model | `tts-1` | TTS |
| TTS voice | `alloy` | TTS |
| TTS speed | `1.0` | TTS |
| PCM resample | `24kHz → 8kHz` (audioop) | Audio |
| Call gap | `180 seconds` | Scheduling |
| Hangup drain | `2.5 seconds` | Call control |
| Recording retry delays | `[3, 5, 8, 13]s` | Download |

---

## Cost Breakdown

| Service | Usage | Cost |
|---------|-------|------|
| Twilio phone number | 1 month | $1.00 |
| Twilio outbound calls | 20 calls × ~1.75 min | $0.49 |
| Twilio recording | 20 recordings | $0.09 |
| Deepgram Nova-2 STT | ~17 min | $0.07 |
| OpenAI GPT-4o-mini | ~160 turns | $0.35 |
| OpenAI TTS-1 | ~160 turns | $0.20 |
| OpenAI GPT-4o (analysis) | 16 transcripts | $0.06 |
| ngrok | free tier | $0.00 |
| **Total** | | **~$2.26** |

---

## Deliverables

| Deliverable | Location |
|-------------|----------|
| Source code | `main.py`, `bot/`, `run_*.py`, `analyze_transcripts.py` |
| 20 call recordings | `recordings/call-CA*.mp3` |
| 16 transcripts | `transcripts/*.txt` |
| Bug report (25 bugs) | `BUG_REPORT.md` |
| Auto-analysis | `AI_ANALYSIS.md` |
| Architecture | `system_architecture_overview.png` |
| Implementation report | `IMPLEMENTATION_REPORT.md` |
| Voice AI improvement plan | `VOICE_AI_ANALYSIS.md` |
| Planning document | `PLAN_README.md` |

---

## Possible Improvements

Based on the VOICE_AI_ANALYSIS.md and IMPLEMENTATION_REPORT.md:

1. **Deepgram Nova-3** — 54% WER reduction; better on non-English names (doctor names were badly garbled)
2. **`endpointing=600ms` + `utterance_end_ms=1200ms`** — eliminates mid-sentence false transcript fires; resolves the "grumpy/chopped" audio quality issue
3. **`tts-1-hd` + voice `nova`** — more natural patient voice; `speed=0.9` prevents consonant clipping at 8kHz
4. **Deepgram Flux model** — native turn detection at ~260ms latency; eliminates the endpointing guesswork entirely
5. **Startup silence guard** — skip the first 6 seconds to avoid responding to the privacy disclaimer

---

*Built by: Bhargav Limbasia | limbasiabb@gmail.com*  
*Challenge: Pretty Good AI Engineering Challenge*
