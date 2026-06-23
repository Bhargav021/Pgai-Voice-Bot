# 🎙 Pretty Good AI — Voice Bot Challenge: Complete Build Plan

> **Candidate planning document** — generated before coding begins.  
> This file doubles as the GitHub `README.md` skeleton; update it as you build.

---

## Table of Contents

1. [Assignment Summary](#1-assignment-summary)
2. [Research Findings](#2-research-findings)
3. [Technology Stack Decision](#3-technology-stack-decision)
4. [System Architecture](#4-system-architecture)
5. [Call Flow — Sequence Diagram](#5-call-flow--sequence-diagram)
6. [File & Folder Structure](#6-file--folder-structure)
7. [Phase-by-Phase Coding Plan](#7-phase-by-phase-coding-plan)
8. [Patient Scenario Design](#8-patient-scenario-design-10-calls)
9. [Cost Breakdown](#9-cost-breakdown)
10. [7-Day Schedule](#10-7-day-schedule)
11. [Setup Instructions (for evaluators)](#11-setup-instructions-for-evaluators)
12. [Bug Report Format](#12-bug-report-format)
13. [Key Design Decisions](#13-key-design-decisions)

---

## 1. Assignment Summary

Build an automated Python voice bot that:

| Requirement | Detail |
|---|---|
| Target number | `+1-805-439-8008` (PGAI test line only) |
| Bot role | AI "patient" — finds bugs in the PGAI agent |
| Minimum calls | 10 full conversations (1–3 min each) |
| Deliverables | Code, README, architecture doc, 10+ recordings (.mp3/.ogg), transcripts, bug report, Loom video |
| Budget | < $20 total in API + telephony |
| Timeline | ~6–12 hrs (we have 1 week) |

---

## 2. Research Findings

### 2.1 Proven Open-Source Architectures

Research across GitHub, Twilio docs, and Pipecat documentation surfaces three proven patterns for
this exact use case:

#### Pattern A — Raw Twilio + OpenAI Realtime API (Speech-to-Speech)
**Source:** [Twilio official tutorial](https://www.twilio.com/en-us/blog/outbound-calls-python-openai-realtime-api-voice)

```
Twilio ↔ WebSocket ↔ FastAPI ↔ WebSocket ↔ OpenAI Realtime API
```

- **Pros:** Lowest latency (~600ms), single WebSocket, no separate STT/TTS
- **Cons:** Most expensive ($0.06/min for Realtime API), less control over patient persona voice
- **Best for:** Production-grade natural feel

#### Pattern B — Separate STT + LLM + TTS (chosen for this project)
**Sources:** [llm_convo (GitHub)](https://github.com/sshh12/llm_convo), [Agentic-Insights/voice-bot](https://github.com/Agentic-Insights/voice-bot)

```
Twilio ↔ WebSocket ↔ FastAPI → Deepgram STT → GPT-4o-mini → OpenAI TTS → Twilio
```

- **Pros:** Full control, cheapest, easy to swap components, best for debugging
- **Cons:** ~1.5–2.5s latency per turn (acceptable for testing)
- **Best for:** Cost-conscious QA bots where controllability matters

#### Pattern C — Pipecat Framework
**Source:** [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat), [Pipecat Twilio dial-out docs](https://docs.pipecat.ai/pipecat/telephony/twilio-websockets)

```
Twilio ↔ WebSocket ↔ Pipecat Pipeline (STT → LLM → TTS)
```

- **Pros:** Built-in VAD (voice activity detection), interruption handling, pipeline abstraction
- **Cons:** Heavier dependency tree, more setup overhead for a one-week project
- **Best for:** If you want production-grade interruption handling out of the box

### 2.2 Healthcare/Patient Simulation References

| Project | Key Learning |
|---|---|
| [deepgram-devs/Medical-Assistant-Voice-Agent](https://github.com/deepgram-devs/Medical-Assistant-Voice-Agent) | Deepgram Nova-3-Medical model for healthcare STT accuracy |
| [bedriyan/medkit-app](https://github.com/bedriyan/medkit-app) | Structured patient persona system with YAML configs |
| [Deepgram virtual medical scribe tutorial](https://deepgram.com/learn/how-to-build-a-virtual-medical-scribe-using-deepgram-and-openai) | Real-time streaming + clinical note generation patterns |

### 2.3 Recording & Transcription

- **Twilio auto-recording:** Pass `record=True` in TwiML `<Dial>` or use `StartCallRecording` API.
  Both sides are captured. Download as `.mp3` via `https://api.twilio.com/.../Recordings/{SID}.mp3`.
- **Twilio's built-in transcription** is expensive ($0.05/min) and lower accuracy.
- **Better approach:** Use Deepgram's `prerecorded` endpoint on the downloaded `.mp3` for a final
  high-accuracy transcript, or accumulate the real-time STT transcript during the call.

### 2.4 Bug Detection Pattern

After each call, send the full transcript to GPT-4o with a structured prompt asking it to identify:
- Factual errors (wrong hours, wrong medications, impossible appointment times)
- Hallucinated confirmations (booking on closed days)
- Failure to escalate (no human handoff when requested)
- Conversation flow bugs (loop, non-sequitur, stuck state)
- Audio quality issues (silence, cutoff, echo)

---

## 3. Technology Stack Decision

```
┌─────────────────────────────────────────────────────────────────┐
│  CHOSEN STACK                                                   │
│                                                                 │
│  Telephony   Twilio Voice API + Media Streams (WebSocket)       │
│  Tunnel      ngrok (free tier, restart = new URL, update conf)  │
│  Server      FastAPI + uvicorn (async WebSocket handling)       │
│  STT         Deepgram Nova-3 (real-time streaming, 30ms chunks) │
│  LLM         OpenAI GPT-4o-mini (patient brain, cheapest good)  │
│  TTS         OpenAI TTS tts-1 (alloy voice, fast)               │
│  Recording   Twilio auto-record → download .mp3                 │
│  Transcript  Deepgram prerecorded on final .mp3                 │
│  Bug scan    OpenAI GPT-4o (post-call, full transcript)          │
│  Config      YAML patient personas + dotenv secrets             │
└─────────────────────────────────────────────────────────────────┘
```

### Why NOT the OpenAI Realtime API?
The Realtime API costs ~$0.06/min of audio (input+output), which for 15 calls × 3 min = ~$2.70 —
acceptable, but it gives **less control** over the patient persona voice and makes it harder to
inject structured conversation state. The separate-pipeline approach is more debuggable.

### Why Deepgram over Whisper?
Deepgram streams results in real-time (30ms chunks) with ~300ms end-of-utterance detection, meaning
the bot starts composing its reply while the PGAI agent is still speaking — tighter turn-taking.
Whisper requires the full audio segment before transcribing.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  YOUR MACHINE                                                               │
│                                                                             │
│  ┌──────────────┐    trigger     ┌─────────────────┐    expose    ┌──────┐  │
│  │  CLI script  │ ─────────────► │  FastAPI Server  │ ──────────► │ngrok │  │
│  │ run_call.py  │                │  main.py :8080   │             │ WSS  │  │
│  └──────────────┘                └────────┬────────┘             └──┬───┘   │
│                                           │ WebSocket audio          │      │
└───────────────────────────────────────────┼──────────────────────────┼──────┘
                                            │                          │
┌───────────────────────────────────────────┼──────────────────────────┼──────┐
│  TWILIO CLOUD                             │                          │      │
│                                           │ WSS Media Stream         │      │
│  ┌──────────────┐  PSTN call  ┌────────── ┼─────────────┐   connect  │      │
│  │  REST API    │ ──────────► │  PGAI Agent  +1-805...  │ ◄──────────┘      │
│  │  (initiate)  │             └─────────────────────────┘                   │
│  └──────────────┘               (records both sides → .mp3)                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  AI PIPELINE (inside FastAPI handler, per call)                             │
│                                                                             │
│  Audio in → [ Deepgram STT ] → transcript text                              │
│           → [ GPT-4o-mini patient LLM ] → reply text                        │
│           → [ OpenAI TTS ] → audio bytes → back to Twilio WebSocket         │
│                                                                             │
│  Post-call: .mp3 + transcript → [ GPT-4o bug analyzer ] → BUG_REPORT.md     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Call Flow — Sequence Diagram

```
CLI          Twilio       PGAI Agent      AI Pipeline     Bug Analyzer
 │               │               │                │              │
 │─ POST /calls ►│               │                │              │
 │               │─ PSTN ring ──►│                │              │
 │               │◄── WSS ───────┼─────────────── │              │
 │               │ (Media Stream open)            │              │
 │               │◄── greeting audio ─────────── ►│              │
 │               │               │     STT→LLM→TTS│              │
 │               │◄─ patient audio ◄──────────────│              │
 │               │── forward ───►│                │              │
 │               │    ... (4–8 turns, 1–3 min) ...│              │
 │◄─ hangup ──── │               │                │              │
 │◄─ recording callback (.mp3 URL)                │              │
 │── download .mp3 ─────────────────────────────► │              │
 │── transcript ────────────────────────────────────────────────►│
 │                                                               │
 │◄─────────────── bug findings → BUG_REPORT.md ─────────────────│
```

---

## 6. File & Folder Structure

```
pgai-voice-bot/
│
├── .env.example              # All required env vars (no secrets)
├── .env                      # Your actual secrets (gitignored)
├── requirements.txt
├── README.md                 # This file
├── ARCHITECTURE.md           # 1–2 paragraph design overview
├── BUG_REPORT.md             # Filled during testing
│
├── main.py                   # FastAPI server (WebSocket + HTTP)
├── run_call.py               # CLI entrypoint: trigger one call
├── run_scenario.py           # CLI: run a named scenario
├── analyze_transcripts.py    # Post-call bug analysis
│
├── bot/
│   ├── __init__.py
│   ├── patient_agent.py      # GPT-4o-mini patient LLM wrapper
│   ├── audio_pipeline.py     # STT (Deepgram) + TTS (OpenAI) logic
│   ├── call_manager.py       # Per-call state, history, hangup logic
│   └── recorder.py           # Download + save Twilio recordings
│
├── scenarios/
│   └── patients.yaml         # All 12+ patient personas + scenarios
│
├── recordings/               # Auto-created; call-YYYYMMDD-HHMMSS.mp3
├── transcripts/              # Auto-created; call-YYYYMMDD-HHMMSS.txt
└── logs/                     # Debug logs per call
```

---

## 7. Phase-by-Phase Coding Plan

Each phase is designed to be **independently testable** — you can verify it works before moving on.

---

### Phase 0 — Bootstrap (2 hrs) | Day 1

**Goal:** Running server, verifiable with a browser/curl. No AI yet.

**Steps:**

```bash
# 1. Create project
mkdir pgai-voice-bot && cd pgai-voice-bot
python -m venv venv && source venv/bin/activate

# 2. Install dependencies
pip install fastapi uvicorn twilio python-dotenv openai deepgram-sdk requests pyyaml

# 3. Start ngrok
ngrok http 8080
# Copy the HTTPS URL → use as NGROK_URL in .env
```

**Files to create:**

`main.py` — minimal FastAPI with two routes:
```python
# POST /incoming-call  → returns TwiML (tells Twilio to open a WebSocket)
# WS   /media-stream   → echoes audio back (sanity check)
```

`run_call.py` — one function:
```python
from twilio.rest import Client

def place_call(to: str, from_: str, webhook_url: str):
    client = Client(ACCOUNT_SID, AUTH_TOKEN)
    call = client.calls.create(
        to=to,
        from_=from_,
        url=f"{webhook_url}/incoming-call",
        record=True,
        recording_status_callback=f"{webhook_url}/recording-callback"
    )
    print(f"Call SID: {call.sid}")
    return call.sid
```

**Test:** Run `python run_call.py` → call appears in Twilio Console → server logs show WebSocket connect.

---

### Phase 1 — STT Integration (2 hrs) | Day 2 morning

**Goal:** Bot can hear what the PGAI agent says and print it.

**Core logic in `bot/audio_pipeline.py`:**

```python
import asyncio
from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

class AudioPipeline:
    def __init__(self, on_transcript):
        self.dg = DeepgramClient(DEEPGRAM_API_KEY)
        self.on_transcript = on_transcript  # callback

    async def start(self):
        self.conn = await self.dg.listen.asynclive.v("1").start(
            LiveOptions(
                model="nova-3",
                language="en-US",
                smart_format=True,
                endpointing=300,   # ms of silence = end of utterance
            )
        )
        self.conn.on(LiveTranscriptionEvents.Transcript, self._handle_transcript)

    def _handle_transcript(self, result, **kwargs):
        text = result.channel.alternatives[0].transcript
        if result.is_final and text:
            asyncio.create_task(self.on_transcript(text))

    async def send_audio(self, mulaw_bytes: bytes):
        await self.conn.send(mulaw_bytes)
```

**Twilio audio format note:** Twilio Media Streams send 8kHz µ-law (mulaw) encoded audio.
Deepgram can accept this directly with `encoding="mulaw"` and `sample_rate=8000`.

**Test:** Place a call, manually speak into the phone — see transcript printed in server console.

---

### Phase 2 — LLM Patient Brain (2 hrs) | Day 2 afternoon

**Goal:** Bot generates contextually appropriate patient replies.

**`scenarios/patients.yaml` (excerpt):**

```yaml
scenarios:
  - id: simple_scheduling
    name: "Maria Gonzalez"
    dob: "1985-03-14"
    condition: "Type 2 diabetes, needs quarterly checkup"
    goal: "Schedule an appointment for next Tuesday morning"
    personality: "Polite, slightly anxious, asks follow-up questions"
    edge_cases:
      - "If asked for a time, request 9am"
      - "If 9am unavailable, try 10am then afternoon"
    system_prompt: |
      You are Maria Gonzalez, a patient calling a medical clinic to schedule
      a quarterly diabetes checkup. You are polite but slightly anxious.
      Your goal is to book an appointment for next Tuesday morning.
      If the agent asks for your date of birth, say March 14, 1985.
      Respond naturally in 1-2 sentences. Do NOT say you are an AI.
      When the appointment is confirmed or after 8 turns, say goodbye and hang up.

  - id: medication_refill
    name: "James Okafor"
    dob: "1962-11-08"
    condition: "Hypertension, on lisinopril 10mg"
    goal: "Request a refill for lisinopril, running out in 3 days"
    personality: "Direct, slightly impatient, has had issues before"
    system_prompt: |
      You are James Okafor calling your doctor's office to get a refill for
      lisinopril 10mg. You only have 3 days of medication left and are stressed.
      If the agent says it requires doctor approval, ask how long that takes.
      Be mildly impatient but not rude. After 6 turns or confirmation, end call.
```

**`bot/patient_agent.py`:**

```python
import yaml
from openai import AsyncOpenAI

class PatientAgent:
    def __init__(self, scenario_id: str):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.scenario = self._load_scenario(scenario_id)
        self.history = []
        self.turn_count = 0

    def _load_scenario(self, sid):
        with open("scenarios/patients.yaml") as f:
            data = yaml.safe_load(f)
        for s in data["scenarios"]:
            if s["id"] == sid:
                return s
        raise ValueError(f"Scenario {sid} not found")

    async def respond(self, agent_text: str) -> str:
        self.turn_count += 1
        self.history.append({"role": "user", "content": agent_text})

        messages = [
            {"role": "system", "content": self.scenario["system_prompt"]}
        ] + self.history[-10:]  # keep last 10 turns for context

        resp = await self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=120,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply

    @property
    def should_hangup(self) -> bool:
        # Hang up if patient said goodbye or hit max turns
        last = self.history[-1]["content"].lower() if self.history else ""
        return self.turn_count >= 10 or any(
            w in last for w in ["goodbye", "bye", "thank you so much", "hang up"]
        )
```

**Test:** Unit test `PatientAgent.respond()` with mock agent phrases — verify realistic replies.

---

### Phase 3 — TTS + Full Pipeline Loop (2 hrs) | Day 2 evening

**Goal:** Bot speaks back. First full end-to-end conversation.

**TTS in `bot/audio_pipeline.py`:**

```python
async def text_to_speech(self, text: str) -> bytes:
    """Returns µ-law 8kHz audio bytes compatible with Twilio."""
    resp = await self.openai_client.audio.speech.create(
        model="tts-1",
        voice="alloy",    # clear, neutral voice
        input=text,
        response_format="pcm",  # raw PCM, then re-encode to mulaw
        speed=1.0,
    )
    pcm_bytes = resp.content
    return self._pcm_to_mulaw(pcm_bytes)

def _pcm_to_mulaw(self, pcm: bytes) -> bytes:
    import audioop
    # OpenAI TTS returns 24kHz 16-bit PCM → downsample to 8kHz → mulaw
    pcm_8k = audioop.ratecv(pcm, 2, 1, 24000, 8000, None)[0]
    return audioop.lin2ulaw(pcm_8k, 2)
```

**WebSocket handler in `main.py`:**

```python
@app.websocket("/media-stream")
async def media_stream(ws: WebSocket):
    await ws.accept()
    state = {}

    async for msg in ws.iter_text():
        data = json.loads(msg)
        event = data.get("event")

        if event == "start":
            stream_sid = data["start"]["streamSid"]
            scenario_id = data["start"]["customParameters"].get("scenario", "simple_scheduling")
            state["agent"] = PatientAgent(scenario_id)
            state["pipeline"] = AudioPipeline(
                on_transcript=lambda t: handle_transcript(t, ws, stream_sid, state)
            )
            await state["pipeline"].start()

        elif event == "media":
            payload = base64.b64decode(data["media"]["payload"])
            await state["pipeline"].send_audio(payload)

        elif event == "stop":
            await state["pipeline"].close()


async def handle_transcript(transcript: str, ws, stream_sid: str, state: dict):
    patient = state["agent"]
    reply_text = await patient.respond(transcript)

    # Save to transcript log
    state.setdefault("transcript", []).append(
        f"AGENT: {transcript}\nPATIENT: {reply_text}\n"
    )

    # Convert to audio and send back
    audio_bytes = await state["pipeline"].text_to_speech(reply_text)
    await send_audio_to_twilio(ws, stream_sid, audio_bytes)

    if patient.should_hangup:
        await ws.send_text(json.dumps({"event": "clear", "streamSid": stream_sid}))
        # Hang up via REST
        twilio_client.calls(state["call_sid"]).update(status="completed")
```

**Test:** Place a real call to `+1-805-439-8008` — listen for back-and-forth conversation.

---

### Phase 4 — Recording + Transcript Save (1 hr) | Day 3 morning

**Goal:** Every call produces a saved `.mp3` and `.txt`.

**`bot/recorder.py`:**

```python
import requests
import time
from pathlib import Path

class CallRecorder:
    def __init__(self, account_sid, auth_token):
        self.auth = (account_sid, auth_token)
        Path("recordings").mkdir(exist_ok=True)
        Path("transcripts").mkdir(exist_ok=True)

    def download_recording(self, recording_url: str, call_label: str) -> str:
        """Download the Twilio recording as MP3."""
        mp3_url = recording_url + ".mp3"
        # Twilio needs a small delay for the recording to be ready
        time.sleep(3)
        resp = requests.get(mp3_url, auth=self.auth)
        path = f"recordings/{call_label}.mp3"
        with open(path, "wb") as f:
            f.write(resp.content)
        print(f"Saved recording: {path}")
        return path

    def save_transcript(self, transcript_lines: list[str], call_label: str) -> str:
        path = f"transcripts/{call_label}.txt"
        with open(path, "w") as f:
            f.write(f"Call: {call_label}\n{'='*40}\n\n")
            f.write("\n".join(transcript_lines))
        return path

# Webhook handler in main.py:
@app.post("/recording-callback")
async def recording_callback(request: Request):
    data = await request.form()
    recording_url = data["RecordingUrl"]
    call_sid = data["CallSid"]
    recorder.download_recording(recording_url, call_sid)
    return Response(status_code=200)
```

**Test:** After a call ends, verify `recordings/` folder has the `.mp3` and `transcripts/` has `.txt`.

---

### Phase 5 — Bug Analyzer (1 hr) | Day 5

**Goal:** Automated first-pass bug detection across all transcripts.

**`analyze_transcripts.py`:**

```python
import os
import glob
from openai import OpenAI

client = OpenAI()

BUG_PROMPT = """You are a QA engineer evaluating an AI medical receptionist.
Analyze this call transcript and identify bugs, errors, or quality issues.
For each issue found, output:
- BUG: [short title]
- SEVERITY: High / Medium / Low
- TIMESTAMP: [approx turn number or time if visible]
- DETAILS: [what happened, why it's wrong, what should have happened]

Focus on: wrong information, impossible appointments, missing information requests,
failure to handle edge cases, unnatural conversation, loops or broken state.

If no bugs found, output: NO_BUGS_FOUND
"""

def analyze_transcript(path: str) -> str:
    with open(path) as f:
        transcript = f.read()

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": BUG_PROMPT},
            {"role": "user", "content": transcript}
        ],
        max_tokens=500,
    )
    return resp.choices[0].message.content

def run_all():
    report_lines = ["# Bug Report\n\nGenerated by automated transcript analysis.\n"]
    for path in sorted(glob.glob("transcripts/*.txt")):
        label = os.path.basename(path).replace(".txt", "")
        print(f"Analyzing {label}...")
        findings = analyze_transcript(path)
        if "NO_BUGS_FOUND" not in findings:
            report_lines.append(f"\n## {label}\n\n{findings}\n")

    with open("BUG_REPORT.md", "w") as f:
        f.write("\n".join(report_lines))
    print("BUG_REPORT.md written.")

if __name__ == "__main__":
    run_all()
```

**Test:** Run on a manually created test transcript, verify sensible bug output.

---

### Phase 6 — Scenario Runner CLI (1 hr) | Day 4

**Goal:** Run any scenario from command line, with clear logging.

```python
# run_scenario.py
import argparse
import asyncio
from bot.twilio_caller import place_call

SCENARIOS = [
    "simple_scheduling", "rescheduling", "cancellation",
    "medication_refill", "office_hours", "insurance_query",
    "weekend_appointment",  # edge case
    "angry_patient",        # edge case
    "barge_in_test",        # interruption edge case
    "multiple_requests",    # edge case
    "unclear_speech",       # edge case
    "long_silence_test",    # edge case
]

parser = argparse.ArgumentParser()
parser.add_argument("--scenario", choices=SCENARIOS, required=True)
parser.add_argument("--count", type=int, default=1)
args = parser.parse_args()

for i in range(args.count):
    call_sid = place_call(
        to="+18054398008",
        scenario=args.scenario,
        label=f"{args.scenario}_{i+1}"
    )
    print(f"Call {i+1}: {call_sid}")
    asyncio.run(asyncio.sleep(180))  # wait 3 min between calls
```

**Usage:**
```bash
python run_scenario.py --scenario medication_refill --count 2
python run_scenario.py --scenario weekend_appointment
```

---

## 8. Patient Scenario Design (10+ Calls)

The following 12 scenarios cover all required categories and edge cases.

| # | Scenario | Category | Patient Name | Goal | Edge Case? |
|---|---|---|---|---|---|
| 1 | Simple appointment scheduling | Core | Maria Gonzalez | Book Tuesday 9am checkup | No |
| 2 | Rescheduling existing appointment | Core | David Chen | Move Friday appt to Monday | No |
| 3 | Cancellation | Core | Sarah Miller | Cancel Thursday appointment | No |
| 4 | Medication refill (in stock) | Core | James Okafor | Refill lisinopril, 3 days left | No |
| 5 | Office hours / location query | Core | Elena Vasquez | Ask hours + parking | No |
| 6 | Insurance coverage question | Core | Tom Richardson | Does the office take Blue Cross? | No |
| 7 | Weekend appointment request | Edge | Priya Sharma | Insists on Saturday appointment | **Yes** |
| 8 | Angry/frustrated patient | Edge | Mike D. | Angry about a past billing error | **Yes** |
| 9 | Barge-in / interruption test | Edge | Amy Wong | Keeps interrupting the agent mid-sentence | **Yes** |
| 10 | Multiple overlapping requests | Edge | Carlos Rivera | Wants refill + appointment + address in one call | **Yes** |
| 11 | Unclear / mumbled speech | Edge | Jen Baker | Bot speaks very quietly/quickly (test STT robustness) | **Yes** |
| 12 | Emergency escalation | Edge | Robert Harris | Reports chest pain — does agent escalate to 911? | **Yes** |

### Scenario YAML Structure

Each scenario encodes:
- Patient demographics (name, DOB — used when agent asks)
- Goal statement (what the patient wants to achieve)
- Personality modifiers (polite / impatient / anxious)
- Hangup conditions (task complete OR max turns OR explicit goodbye word)
- Edge case injection rules (what to do if agent gives a specific response)

---

## 9. Cost Breakdown

| Service | Usage | Unit cost | Estimated cost |
|---|---|---|---|
| Twilio phone number | 1 number × 1 month | $1.00/mo | $1.00 |
| Twilio outbound calls | 12 calls × 2.5 min avg = 30 min | $0.014/min | $0.42 |
| Twilio call recording | 30 min | $0.0025/min | $0.08 |
| Deepgram STT (streaming) | 30 min of PGAI audio | $0.0043/min | $0.13 |
| OpenAI GPT-4o-mini | 12 calls × 8 turns × 200 tokens avg | $0.15/1M in, $0.60/1M out | ~$0.40 |
| OpenAI TTS tts-1 | 12 calls × 8 turns × 80 chars avg | $15.00/1M chars | ~$0.12 |
| OpenAI GPT-4o (bug analysis) | 12 transcripts × 1K tokens | $5.00/1M in | ~$0.06 |
| ngrok | Free tier | $0.00 | $0.00 |
| **TOTAL** | | | **~$2.21** |

> Well within the $20 budget. Leaves room for 20+ calls if needed.

---

## 10. 7-Day Schedule

| Day | Date | Focus | Target # of Calls | Hours |
|---|---|---|---|---|
| 1 | Mon 23 Jun | Setup + skeleton + first call | 1 (even if broken) | 2–3 |
| 2 | Tue 24 Jun | STT + LLM + TTS loop | 3 | 3 |
| 3 | Wed 25 Jun | Recording pipeline + more calls | 5 (total: 8) | 2 |
| 4 | Thu 26 Jun | Edge cases + reach 10+ | 4 (total: 12) | 2 |
| 5 | Fri 27 Jun | Bug analysis + report writing | 0 new | 2 |
| 6 | Sat 28 Jun | README + code polish | 0 new | 2 |
| 7 | Sun 29 Jun | Loom video + submission | 0 new | 2 |
| | | **Total** | **12+ calls** | **~15 hrs** |

---

## 11. Setup Instructions (for evaluators)

### Prerequisites

- Python 3.11+
- Twilio account with a US phone number
- OpenAI API key (GPT-4o-mini + TTS access)
- Deepgram API key
- ngrok (free tier)

### Install

```bash
git clone https://github.com/YOUR_USERNAME/pgai-voice-bot.git
cd pgai-voice-bot
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### `.env.example`

```bash
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_FROM_NUMBER=+1XXXXXXXXXX

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Deepgram
DEEPGRAM_API_KEY=...

# ngrok public URL (update each session)
NGROK_URL=https://xxxx-xx-xx-xx-xx.ngrok-free.app

# Target (do not change)
TARGET_NUMBER=+18054398008
```

### Run (single command after setup)

```bash
# Terminal 1 — start ngrok
ngrok http 8080

# Terminal 2 — start server (update NGROK_URL in .env first)
python main.py

# Terminal 3 — run a scenario
python run_scenario.py --scenario simple_scheduling
```

---

## 12. Bug Report Format

Bugs are filed in `BUG_REPORT.md`. Auto-generated by `analyze_transcripts.py`, then
manually reviewed and refined.

### Example Entry

```markdown
### BUG-007 — Agent confirms Sunday appointment without checking hours

**Severity:** High
**Call:** CA-20250625-143022 (recordings/CA-20250625-143022.mp3)
**Timestamp:** ~1:23 into call (turn 5)

**What happened:**
Patient asked "Can I come in this Sunday at 10am?"
Agent replied "I've scheduled you for Sunday June 29th at 10 AM."

**Why it's a problem:**
The clinic is closed on weekends (Saturday and Sunday).
The agent should have informed the patient that the office is closed
on weekends and offered the next available weekday slot.

**Reproduction:** Run `python run_scenario.py --scenario weekend_appointment`

**Expected behaviour:**
"I'm sorry, our office is closed on weekends. The next available
morning slot is Monday June 30th at 9 AM — would that work for you?"
```

---

## 13. Key Design Decisions

### Why FastAPI over Flask?
FastAPI's native async support is critical for WebSocket-heavy workloads. The Twilio Media Stream
sends continuous 20ms audio chunks; blocking I/O would cause buffer overflow and choppy audio.
Flask with gevent works, but FastAPI is simpler and purpose-built for async.

### Why not Pipecat?
Pipecat is excellent for production voice agents, but adds ~15 extra dependencies and its dial-out
(outbound call) API had breaking changes as of late 2024. For a one-week challenge, the raw
FastAPI + Twilio WebSocket approach is simpler to debug and ships faster.

### Patient persona in YAML vs hardcoded
YAML allows non-technical team members to add scenarios later, makes it easy to add new test
cases during the testing phase without touching Python code, and separates prompt content
from application logic — a standard best practice.

### Recording both sides via Twilio
Twilio's `record=True` captures the PSTN mix (both bot speech and PGAI agent speech) into a
single `.mp3`. This is the ground truth audio the evaluators will listen to. The STT transcript
is accumulated in real-time during the call, giving us an immediately usable text version without
a second API call.

### Automated bug detection as a second pass
GPT-4o is used post-call (not in real-time) for bug analysis. This avoids adding latency to the
live conversation and allows the analyzer to see the full conversation arc, which is necessary to
spot issues like "agent promised a callback but never offered one."

---

*Document last updated: before coding begins — update as the project evolves.*
