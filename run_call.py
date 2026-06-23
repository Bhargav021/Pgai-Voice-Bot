"""
run_call.py — low-level Twilio call trigger.
Places a single outbound call to the PGAI test line for a given scenario.

Usage:
    python run_call.py --scenario simple_scheduling
    python run_call.py --scenario medication_refill --no-record
"""

import os
import sys
import argparse
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_call")


def place_call(scenario: str = "simple_scheduling", record: bool = True) -> str:
    """
    Initiates an outbound PSTN call via Twilio REST API.

    The call flow:
      1. Twilio calls TARGET_NUMBER (+1-805-439-8008)
      2. When answered, Twilio fetches TwiML from NGROK_URL/incoming-call?scenario=...
      3. TwiML tells Twilio to open a Media Stream WebSocket to our FastAPI server
      4. Audio flows: PGAI agent <-> Twilio <-> WebSocket <-> our bot AI pipeline

    Returns:
        Twilio Call SID (use to monitor at console.twilio.com)
    """
    # Validate required env vars
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")
    to_number   = os.getenv("TARGET_NUMBER", "+18054398008")
    ngrok_url   = os.getenv("NGROK_URL", "").rstrip("/")

    missing = [k for k, v in {
        "TWILIO_ACCOUNT_SID": account_sid,
        "TWILIO_AUTH_TOKEN":  auth_token,
        "TWILIO_FROM_NUMBER": from_number,
        "NGROK_URL":          ngrok_url,
    }.items() if not v]

    if missing:
        log.error(f"Missing required env vars: {', '.join(missing)}")
        log.error("Check your .env file.")
        sys.exit(1)

    from twilio.rest import Client
    client = Client(account_sid, auth_token)

    webhook_url  = f"{ngrok_url}/incoming-call?scenario={scenario}"
    recording_cb = f"{ngrok_url}/recording-callback"
    status_cb    = f"{ngrok_url}/call-status"

    log.info("=" * 55)
    log.info(f"Placing call: {from_number} -> {to_number}")
    log.info(f"Scenario:     {scenario}")
    log.info(f"Webhook:      {webhook_url}")
    log.info(f"Recording:    {'enabled' if record else 'disabled'}")
    log.info("=" * 55)

    call = client.calls.create(
        to=to_number,
        from_=from_number,
        url=webhook_url,
        method="POST",
        record=record,
        recording_status_callback=recording_cb if record else None,
        recording_status_callback_method="POST",
        status_callback=status_cb,
        status_callback_method="POST",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        timeout=60,          # Seconds to wait for answer before giving up
    )

    log.info(f"Call initiated! SID: {call.sid}")
    log.info(f"Monitor at: https://console.twilio.com/us1/monitor/calls/{call.sid}")
    return call.sid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a single PGAI test call")
    parser.add_argument(
        "--scenario", default="simple_scheduling",
        help="Scenario ID from scenarios/patients.yaml"
    )
    parser.add_argument(
        "--no-record", action="store_true",
        help="Disable call recording (saves cost during debugging)"
    )
    args = parser.parse_args()

    sid = place_call(scenario=args.scenario, record=not args.no_record)
    print(f"\n✓ Call SID: {sid}")