"""
AudioPipeline — Deepgram real-time STT + OpenAI TTS for one call.

Inbound:  raw µ-law 8 kHz audio bytes from Twilio Media Streams
          → Deepgram Nova-2 live transcription
          → on_transcript(text) callback

Outbound: text reply from PatientAgent
          → OpenAI TTS tts-1 (raw 24 kHz PCM)
          → resample to 8 kHz → encode to µ-law → base64
          → returned to main.py for injection into Twilio WebSocket
"""

import os
import base64
import logging
import asyncio

log = logging.getLogger(__name__)

# ── audioop: stdlib ≤3.12; audioop-lts installs as 'audioop' on 3.13+ ────────
try:
    import audioop   # works on stdlib AND after `pip install audioop-lts`
    _HAS_AUDIOOP = True
except ModuleNotFoundError:
    log.warning(
        "audioop not available — TTS will be silent. "
        "Run: pip install audioop-lts"
    )
    _HAS_AUDIOOP = False
    audioop = None  # type: ignore[assignment]


class AudioPipeline:
    """Manages one call's Deepgram STT connection and OpenAI TTS."""

    def __init__(self, on_transcript):
        """
        on_transcript: coroutine function(text: str) → None
            Called with each final Deepgram transcript segment.
        """
        self.on_transcript = on_transcript
        self._dg_conn      = None
        self._openai       = None
        self._dg_client    = None
        self.listening     = True   # set False during TTS playback to prevent echo

        # ── Deepgram ──────────────────────────────────────────────────────────
        dg_key = os.getenv("DEEPGRAM_API_KEY")
        if dg_key:
            try:
                from deepgram import DeepgramClient
                self._dg_client = DeepgramClient(dg_key)
                log.debug("DeepgramClient ready")
            except ImportError:
                log.error("deepgram-sdk not installed. Run: pip install deepgram-sdk")
        else:
            log.warning("DEEPGRAM_API_KEY not set — STT disabled")

        # ── OpenAI TTS ────────────────────────────────────────────────────────
        oai_key = os.getenv("OPENAI_API_KEY")
        if oai_key:
            from openai import AsyncOpenAI
            self._openai = AsyncOpenAI(api_key=oai_key)
        else:
            log.warning("OPENAI_API_KEY not set — TTS disabled")

    # ── STT: open Deepgram WebSocket ─────────────────────────────────────────

    async def start(self) -> None:
        """Open the Deepgram live-transcription WebSocket for this call.

        Deepgram SDK v3 pattern:
          1. Create the connection object first (do NOT call .start() yet)
          2. Register event handlers on the connection object
          3. Call .start(options) — returns True/False, not the connection
        """
        if not self._dg_client:
            return
        try:
            from deepgram import LiveOptions, LiveTranscriptionEvents

            # Step 1: create the connection object
            conn = self._dg_client.listen.asynclive.v("1")

            # Step 2: register handlers BEFORE starting
            conn.on(LiveTranscriptionEvents.Transcript, self._on_deepgram_transcript)
            conn.on(LiveTranscriptionEvents.Error,      self._on_deepgram_error)
            conn.on(LiveTranscriptionEvents.Close,      self._on_deepgram_close)

            # Step 3: open the WebSocket (returns bool, NOT the connection)
            options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="mulaw",       # Twilio sends µ-law
                sample_rate=8000,       # Twilio sends 8 kHz
                channels=1,
                endpointing=300,        # 300 ms silence -> end-of-utterance
                interim_results=False,
                # utterance_end_ms omitted: causes HTTP 400 on Deepgram SDK 3.7.4
            )
            success = await conn.start(options)
            if success is False:
                log.error("Deepgram .start() returned False — check API key and model name")
                self._dg_conn = None
                return

            self._dg_conn = conn
            log.info("Deepgram STT connection open")
        except Exception as e:
            log.error(f"Deepgram connection failed: {e}")
            self._dg_conn = None

    # ── STT: receive transcript ───────────────────────────────────────────────

    async def _on_deepgram_transcript(self, _conn, result=None, **kwargs) -> None:
        """SDK v3 asynclive requires async handlers — SDK does `await handler(...)`.
        Sync handlers return None, causing 'a coroutine was expected, got None' crash."""
        if result is None:
            return
        try:
            alt  = result.channel.alternatives[0]
            text = alt.transcript.strip()
            if result.is_final and text:
                log.info(f"[STT final] {text}")
                self.on_transcript(text)  # lambda in main.py schedules the task
        except Exception as e:
            log.error(f"Transcript handler error: {e}")

    async def _on_deepgram_error(self, _conn, error=None, **kwargs) -> None:
        log.error(f"[Deepgram ERROR] {error}")

    async def _on_deepgram_close(self, _conn, close=None, **kwargs) -> None:
        log.warning("[Deepgram CLOSED]")
        self._dg_conn = None

    # ── STT: forward audio ───────────────────────────────────────────────────

    async def send_audio(self, mulaw_bytes: bytes) -> None:
        """Forward raw µ-law bytes from Twilio WebSocket to Deepgram.
        Skipped when listening=False (during our own TTS playback) to prevent echo."""
        if self._dg_conn and self.listening:
            try:
                await self._dg_conn.send(mulaw_bytes)
            except Exception as e:
                log.debug(f"Deepgram send error (call may have ended): {e}")

    # ── TTS: text → µ-law base64 ─────────────────────────────────────────────

    async def text_to_speech_b64(self, text: str) -> str | None:
        """
        Convert reply text to Twilio-compatible µ-law 8 kHz audio.

        Pipeline:
          OpenAI tts-1 → raw PCM 24 kHz 16-bit mono
          → audioop.ratecv  downsample to 8 kHz
          → audioop.lin2ulaw encode to µ-law
          → base64 for Twilio media WebSocket message

        Returns:
            base64-encoded µ-law string, or None on failure.
        """
        if not self._openai:
            log.warning("TTS skipped — OpenAI not configured")
            return None
        if not _HAS_AUDIOOP:
            log.warning("TTS skipped — audioop not available")
            return None

        try:
            resp = await self._openai.audio.speech.create(
                model="tts-1",
                voice="alloy",          # clear, neutral, gender-neutral
                input=text,
                response_format="pcm",  # raw signed 16-bit PCM at 24 kHz
                speed=1.0,
            )
            pcm_24k: bytes = resp.content

            # Downsample 24 kHz → 8 kHz (required by Twilio)
            pcm_8k, _ = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)

            # Encode linear PCM → µ-law
            mulaw_8k: bytes = audioop.lin2ulaw(pcm_8k, 2)

            return base64.b64encode(mulaw_8k).decode("ascii")

        except Exception as e:
            log.error(f"TTS error: {e}")
            return None

    # ── Cleanup ──────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Gracefully shut down the Deepgram WebSocket."""
        if self._dg_conn:
            try:
                await self._dg_conn.finish()
                log.info("Deepgram STT connection closed")
            except Exception:
                pass
            finally:
                self._dg_conn = None