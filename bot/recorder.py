"""
CallRecorder — downloads Twilio call recordings and saves call transcripts.

Recording download uses exponential back-off because Twilio's recording
callback fires 1–3 s before the .mp3 file is actually accessible via REST.
"""

import time
import logging
from pathlib import Path

import requests

log = logging.getLogger(__name__)


class CallRecorder:

    def __init__(self, account_sid: str, auth_token: str):
        self.auth = (account_sid, auth_token) if account_sid and auth_token else None
        Path("recordings").mkdir(exist_ok=True)
        Path("transcripts").mkdir(exist_ok=True)

    # ── Recording download ───────────────────────────────────────────────────

    def download_recording(self, recording_url: str, call_label: str) -> str | None:
        """
        Download the Twilio dual-channel recording as .mp3.

        Twilio fires the recording-callback ~1 s after the file is queued,
        but the file may not be readable for another 2–5 s.
        We retry up to 4 times with increasing delays.

        Args:
            recording_url: URL from Twilio callback (no extension)
            call_label:    Used as the filename stem

        Returns:
            Local path to saved .mp3, or None on failure.
        """
        if not self.auth:
            log.warning("Twilio credentials not set — cannot download recording")
            return None

        mp3_url = recording_url.rstrip("/") + ".mp3"
        path    = f"recordings/{call_label}.mp3"

        delays = [3, 5, 8, 13]    # seconds between attempts (Fibonacci-ish)
        for attempt, delay in enumerate(delays, start=1):
            try:
                log.info(f"Downloading recording (attempt {attempt}/{len(delays)}): {mp3_url}")
                time.sleep(delay)
                resp = requests.get(mp3_url, auth=self.auth, timeout=30)

                if resp.status_code == 200 and len(resp.content) > 500:
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    size_kb = len(resp.content) // 1024
                    log.info(f"Recording saved: {path} ({size_kb} KB)")
                    return path

                log.warning(
                    f"Recording not ready — HTTP {resp.status_code}, "
                    f"body length {len(resp.content)} bytes"
                )
            except requests.RequestException as e:
                log.error(f"Download error on attempt {attempt}: {e}")

        log.error(f"Failed to download recording after {len(delays)} attempts: {mp3_url}")
        return None

    # ── Transcript save ──────────────────────────────────────────────────────

    def save_transcript(self, lines: list[str], call_label: str) -> str:
        """
        Write the accumulated AGENT/PATIENT exchange to a .txt file.

        Args:
            lines:      List of strings like "AGENT: hello" / "PATIENT: hi"
            call_label: Used as the filename stem

        Returns:
            Local path to saved .txt.
        """
        path = f"transcripts/{call_label}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Call: {call_label}\n")
            f.write("=" * 50 + "\n\n")
            f.write("\n".join(lines))
            f.write("\n")
        log.info(f"Transcript saved: {path}")
        return path