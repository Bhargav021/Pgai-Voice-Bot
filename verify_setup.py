"""
verify_setup.py — Pre-flight check before the first real call.

Tests each API key and confirms all services are reachable.
Run this AFTER filling in your .env but BEFORE starting the server.

Usage:
    python verify_setup.py
    python verify_setup.py --skip-deepgram   (if you don't have the key yet)
"""

import os
import sys
import argparse
import textwrap
from pathlib import Path
from dotenv import load_dotenv

# Force UTF-8 output on Windows so box-drawing chars print correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
WARN = "\033[93m⚠ WARN\033[0m"
SEP  = "─" * 55

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    if detail:
        for line in textwrap.wrap(detail, 70):
            print(f"         {line}")


# ── 1. .env exists and has required keys ─────────────────────────────────────
print(f"\n{SEP}")
print("  1. Environment / .env file")
print(SEP)

required_keys = [
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "OPENAI_API_KEY",
    "DEEPGRAM_API_KEY",
    "NGROK_URL",
]

env_file = Path(".env")
check(".env file exists", env_file.exists(),
      "Create one with: cp .env.example .env" if not env_file.exists() else "")

for key in required_keys:
    val = os.getenv(key, "")
    present = bool(val) and "xxxx" not in val.lower() and "your_" not in val.lower()
    check(f"{key} is set", present,
          f"Current value: '{val[:30]}...'" if val and not present else "")

# ── 2. Python version ─────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  2. Python & dependencies")
print(SEP)

major, minor = sys.version_info.major, sys.version_info.minor
check(f"Python {major}.{minor} (need 3.10+)", major == 3 and minor >= 10,
      f"Found: {sys.version}")

# Check audioop — audioop-lts installs as the 'audioop' module on all Python versions
try:
    import audioop  # type: ignore[attr-defined]  # noqa: F401
    label = "audioop-lts installed (Python 3.13+)" if minor >= 13 else "audioop available (stdlib)"
    check(label, True)
except ModuleNotFoundError:
    if minor >= 13:
        check("audioop-lts installed", False, "Run: pip install audioop-lts")
    else:
        check("audioop available", False, "Unexpected — check Python installation")

# Check critical packages
packages = [
    ("fastapi",     "fastapi"),
    ("uvicorn",     "uvicorn"),
    ("twilio",      "twilio"),
    ("openai",      "openai"),
    ("deepgram",    "deepgram"),
    ("yaml",        "pyyaml"),
    ("dotenv",      "python-dotenv"),
]
for mod, pip_name in packages:
    try:
        __import__(mod)
        check(f"{pip_name} importable", True)
    except ImportError:
        check(f"{pip_name} importable", False,
              f"Run: pip install {pip_name}")

# ── 3. Twilio credentials ─────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  3. Twilio")
print(SEP)

account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
auth_token  = os.getenv("TWILIO_AUTH_TOKEN", "")
from_number = os.getenv("TWILIO_FROM_NUMBER", "")

if account_sid and auth_token:
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        # List phone numbers — low-cost API call
        numbers = list(client.incoming_phone_numbers.list(limit=5))
        check("Twilio credentials valid", True,
              f"Account has {len(numbers)} number(s)")
        if from_number:
            found = any(n.phone_number == from_number for n in numbers)
            check(f"FROM number {from_number} exists in account", found,
                  "Check TWILIO_FROM_NUMBER in .env" if not found else "")
        else:
            check("TWILIO_FROM_NUMBER set", False,
                  "Set TWILIO_FROM_NUMBER to your Twilio number")
    except Exception as e:
        check("Twilio credentials valid", False, str(e))
else:
    check("Twilio credentials provided", False,
          "Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env")

# ── 4. OpenAI ─────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  4. OpenAI (LLM + TTS)")
print(SEP)

oai_key = os.getenv("OPENAI_API_KEY", "")
if oai_key:
    try:
        from openai import OpenAI
        client_oai = OpenAI(api_key=oai_key)

        # LLM check
        resp = client_oai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        check("OpenAI GPT-4o-mini accessible", True,
              f"Response: {resp.choices[0].message.content}")

        # TTS check
        tts_resp = client_oai.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input="Test.",
            response_format="pcm",
        )
        tts_bytes = len(tts_resp.content)
        check("OpenAI TTS (tts-1) accessible", tts_bytes > 100,
              f"Got {tts_bytes} PCM bytes")
    except Exception as e:
        check("OpenAI API accessible", False, str(e))
else:
    check("OpenAI API key provided", False, "Set OPENAI_API_KEY in .env")

# ── 5. Deepgram ───────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  5. Deepgram STT")
print(SEP)

dg_key = os.getenv("DEEPGRAM_API_KEY", "")
if dg_key:
    try:
        import requests
        r = requests.get(
            "https://api.deepgram.com/v1/projects",
            headers={"Authorization": f"Token {dg_key}"},
            timeout=10,
        )
        if r.status_code == 200:
            projects = r.json().get("projects", [])
            check("Deepgram API key valid", True,
                  f"{len(projects)} project(s) found")
        else:
            check("Deepgram API key valid", False,
                  f"HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        check("Deepgram API reachable", False, str(e))
else:
    check("Deepgram API key provided", False, "Set DEEPGRAM_API_KEY in .env")

# ── 6. ngrok URL ──────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  6. ngrok tunnel")
print(SEP)

ngrok_url = os.getenv("NGROK_URL", "").rstrip("/")
if ngrok_url and "xxxx" not in ngrok_url:
    try:
        import requests
        r = requests.get(f"{ngrok_url}/health", timeout=8)
        if r.status_code == 200:
            check(f"ngrok → server reachable ({ngrok_url})", True,
                  "Server is live and responding")
        else:
            check("ngrok URL reachable", False,
                  f"HTTP {r.status_code} — is main.py running?")
    except Exception as e:
        check("ngrok URL reachable", False,
              f"{e}\nStart main.py first, then re-run this check")
else:
    check("NGROK_URL set in .env", False,
          "Start ngrok (ngrok http 8080) and paste the URL into .env")

# ── 7. Scenarios file ─────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  7. Scenarios")
print(SEP)

yaml_path = Path("scenarios/patients.yaml")
if yaml_path.exists():
    try:
        import yaml
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        ids = [s["id"] for s in data.get("scenarios", [])]
        check("scenarios/patients.yaml valid", True,
              f"{len(ids)} scenario(s): {', '.join(ids)}")
    except Exception as e:
        check("scenarios/patients.yaml parseable", False, str(e))
else:
    check("scenarios/patients.yaml exists", False,
          "Run setup.ps1 or create the file manually")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print("  SUMMARY")
print(SEP)

passed  = sum(1 for _, ok, _ in results if ok)
failed  = sum(1 for _, ok, _ in results if not ok)
total   = len(results)

print(f"  {passed}/{total} checks passed")
if failed:
    print(f"\n  {FAIL} Items to fix:")
    for label, ok, detail in results:
        if not ok:
            print(f"    • {label}")
            if detail:
                for line in textwrap.wrap(detail, 65):
                    print(f"      {line}")
    print()
    sys.exit(1)
else:
    print(f"\n  {PASS} All checks passed — you're ready to make calls!")
    print(f"\n  Run your first call:")
    print(f"    python run_scenario.py --scenario simple_scheduling")
    print()
    sys.exit(0)
