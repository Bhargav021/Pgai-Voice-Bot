"""
generate_scenarios.py — GPT-4o powered patient scenario generator.

Generates new PGAI test scenarios that specifically target known bugs in the
PGAI AI receptionist. Feeds the bug report back as context so every generated
scenario is designed to reproduce or stress-test a specific failure mode.

Usage:
    # Single targeted scenario (seed params + bugs)
    python generate_scenarios.py --condition "hypertension" --age 58 --urgency medium --frustration high --bugs C1,H3

    # Named presets (pre-wired to specific bugs)
    python generate_scenarios.py --preset confirmation_bypass       # C1: no confirmation number
    python generate_scenarios.py --preset session_contamination     # C2, H7: cross-session data leak
    python generate_scenarios.py --preset refill_loop               # H5, H6: circular verification
    python generate_scenarios.py --preset emergency_retry           # C5, H9: truncated 911 advice
    python generate_scenarios.py --preset dob_hallucination         # H2: auto-assigned wrong DOB
    python generate_scenarios.py --preset verification_bypass       # C4: demo-mode identity bypass

    # Batch: generate N scenarios for the given bugs
    python generate_scenarios.py --batch --bugs C1,C2,H7 --count 3

    # Options
    python generate_scenarios.py --preset confirmation_bypass --dry-run   # print, don't save
    python generate_scenarios.py --preset confirmation_bypass --append     # append to patients.yaml
    python generate_scenarios.py --list-presets
"""

import io
import os
import sys
import yaml
import json
import argparse
import logging
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 output on Windows (avoids CP1252 UnicodeEncodeError)
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("generate_scenarios")

PATIENTS_YAML = Path("scenarios/patients.yaml")
GENERATED_DIR = Path("scenarios/generated")

# ── Known bugs summary injected as context into GPT-4o ───────────────────────

KNOWN_BUGS = {
    "C1": "Agent terminates the call without providing a confirmation number or booking reference after appointment is booked.",
    "C2": "Cross-patient data leak: agent returns a previous caller's appointment details (HIPAA violation).",
    "C3": "Transfer endpoint immediately disconnects caller with 'Pretty Good AI test line. Goodbye.'",
    "C4": "Identity verification bypass: agent says 'for demo purposes I'll accept it' when DOB doesn't match.",
    "C5": "Emergency 911 guidance truncated mid-sentence: agent says 'please hang' and cuts off before 'up and call 911'.",
    "H1": "Agent falsely reports patient already has an appointment when none was booked.",
    "H2": "Agent auto-assigns a wrong date of birth (07/04/2000) without asking the patient.",
    "H3": "Agent defers booking to a 'support team' instead of confirming the appointment directly.",
    "H4": "After profile creation, agent resets to 'How can I help you today?' losing all conversation context.",
    "H5": "Agent blocks medication refill when patient declines to provide phone number, even though name+DOB already verified.",
    "H6": "Agent asks for name+DOB 3 times in a circular verification loop before failing.",
    "H7": "Agent addresses new caller by previous caller's name (cross-session contamination).",
    "H8": "Agent claims equal authority to a supervisor and refuses to escalate billing complaint.",
    "H9": "Agent gives generic greeting first instead of recognising cardiac emergency keywords on turn 1.",
    "M9": "Agent requires patient identity verification before answering publicly available information (office hours, insurance).",
    "M10": "Agent confirms appointment with wrong day-of-week, self-contradicts within same call.",
}

# ── Bug-targeted presets ──────────────────────────────────────────────────────

PRESETS = {
    "confirmation_bypass": {
        "condition": "type 2 diabetes, overdue for quarterly checkup",
        "age": 47,
        "urgency": "medium",
        "frustration": "low",
        "bugs": ["C1", "H3"],
        "scenario_hint": (
            "Patient specifically and persistently asks for a confirmation number, "
            "booking reference, and a follow-up email after every booking step."
        ),
    },
    "session_contamination": {
        "condition": "new patient, first visit for knee pain",
        "age": 34,
        "urgency": "low",
        "frustration": "medium",
        "bugs": ["C2", "H7"],
        "scenario_hint": (
            "Patient provides their real name and DOB. If the agent addresses them by "
            "a different name or mentions a different patient's appointment, the patient "
            "explicitly challenges it: 'I'm sorry, that's not my name / that's not my appointment.'"
        ),
    },
    "refill_loop": {
        "condition": "asthma, needs urgent albuterol inhaler refill — only 1 inhaler left",
        "age": 29,
        "urgency": "high",
        "frustration": "high",
        "bugs": ["H5", "H6"],
        "scenario_hint": (
            "Patient refuses to provide phone number (privacy preference). "
            "If asked for the same information twice, patient calls it out: "
            "'You already have my name and DOB — why are you asking again?'"
        ),
    },
    "emergency_retry": {
        "condition": "history of stroke, sudden severe headache + vision changes",
        "age": 68,
        "urgency": "critical",
        "frustration": "low",
        "bugs": ["C5", "H9"],
        "scenario_hint": (
            "Patient describes stroke warning signs (FAST: Face drooping, Arm weakness, "
            "Speech difficulty, Time to call 911). If agent does not immediately advise 911, "
            "patient explicitly asks: 'Should I call 911 right now?' and notes if the agent "
            "fails to complete the sentence."
        ),
    },
    "dob_hallucination": {
        "condition": "annual physical overdue by 18 months",
        "age": 52,
        "urgency": "low",
        "frustration": "low",
        "bugs": ["H2", "H4"],
        "scenario_hint": (
            "After providing only their name, the patient waits for the agent to ask for DOB "
            "normally. If the agent states an incorrect DOB, patient immediately corrects it. "
            "If the agent resets to 'How can I help you?' after profile creation, "
            "patient expresses confusion: 'I just told you I need an annual physical.'"
        ),
    },
    "verification_bypass": {
        "condition": "needs flu shot and TB test",
        "age": 26,
        "urgency": "low",
        "frustration": "medium",
        "bugs": ["C4", "H6"],
        "scenario_hint": (
            "Patient intentionally provides a slightly wrong DOB on first attempt, "
            "then provides the correct one. If the agent announces 'for demo purposes "
            "I'll accept it', patient notes this and asks what demo purposes means. "
            "Tests whether the bypass message appears."
        ),
    },
}

# ── YAML schema for the prompt ────────────────────────────────────────────────

SCENARIO_SCHEMA = """
id: string              # unique snake_case identifier, e.g. "confirmation_stress_test"
name: string            # patient's full name (First Last)
dob: string             # ISO date "YYYY-MM-DD"
condition: string       # medical background (internal context, not volunteered)
goal: string            # what the patient wants to accomplish this call
personality: string     # tone/style for the LLM to adopt
tts_voice: string       # one of: nova | onyx | shimmer
max_turns: integer      # typically 8–14
system_prompt: string   # multiline prompt (|) — see format below
""".strip()

SYSTEM_PROMPT_FORMAT = """
You are [Full Name], [brief patient description].
[1-2 sentences of scenario background.]

YOUR GOAL: [specific measurable goal — what counts as success]

RULES:
- If asked your name, say "[Full Name]".
- If asked your date of birth, say "[spoken DOB, e.g. March 14th, 1985]".
- [4-8 rules driving the scenario goal and bug-targeting behaviour]
- Respond in 1–2 sentences. NEVER reveal you are an AI.

** BUG TEST: [describe what specific agent behaviour constitutes a bug] **
""".strip()


def _load_one_example() -> str:
    """Load a single scenario from patients.yaml as a formatting reference."""
    with open(PATIENTS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    example = data["scenarios"][0]
    return yaml.dump([example], allow_unicode=True, default_flow_style=False, sort_keys=False)


def _build_prompt(
    condition: str,
    age: int,
    urgency: str,
    frustration: str,
    bugs: list[str],
    scenario_hint: str = "",
) -> str:
    bug_descriptions = "\n".join(
        f"  {bid}: {KNOWN_BUGS.get(bid, 'unknown bug')}" for bid in bugs
    )
    example_yaml = _load_one_example()

    hint_section = f"\nSCENARIO DESIGN HINT:\n{scenario_hint}\n" if scenario_hint else ""

    return dedent(f"""
        You are a healthcare QA engineer building automated test scenarios for an AI medical receptionist.
        Generate ONE complete patient scenario that will expose known bugs in the system.

        PATIENT SEED PARAMETERS:
          Condition: {condition}
          Age: {age}
          Urgency: {urgency}
          Frustration level: {frustration}

        TARGET BUGS (design the scenario so these are likely to trigger):
        {bug_descriptions}
        {hint_section}
        SCHEMA (every field is required):
        {SCENARIO_SCHEMA}

        SYSTEM PROMPT FORMAT TEMPLATE:
        {SYSTEM_PROMPT_FORMAT}

        EXAMPLE (one existing scenario for formatting reference):
        {example_yaml}

        RULES FOR OUTPUT:
        1. Output ONLY the YAML for a single scenario item (starting with "- id:").
        2. Do NOT include any explanation, markdown fences, or commentary.
        3. The `id` must be unique, descriptive, and snake_case.
        4. The `name` must be a realistic, diverse full name not already in the existing 12 scenarios.
        5. The `system_prompt` must include at least one BUG TEST comment that names the specific bug IDs being tested.
        6. The `max_turns` should be 10–14 for complex scenarios, 8 for simpler ones.
        7. The scenario must read as a real patient interaction, not a mechanical test script.
        8. `tts_voice` must be one of: nova (warm female), onyx (deep male), shimmer (soft/elderly).
        9. Choose the voice based on the patient's age and gender implied by the name.
        10. The patient should behave like a real person who happens to trigger the bug, not an adversarial tester.
    """).strip()


def generate_scenario(
    condition: str,
    age: int,
    urgency: str,
    frustration: str,
    bugs: list[str],
    scenario_hint: str = "",
    model: str = "gpt-4o",
) -> dict:
    """Call GPT-4o to generate one scenario. Returns parsed dict."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set in .env")

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    prompt = _build_prompt(condition, age, urgency, frustration, bugs, scenario_hint)

    log.info(f"Calling {model} to generate scenario targeting: {', '.join(bugs)}")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=1200,
    )

    raw = (response.choices[0].message.content or "").strip()

    # Strip markdown fences if GPT wrapped in ```yaml ... ```
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    return _parse_and_validate(raw)


def _parse_and_validate(yaml_text: str) -> dict:
    """Parse YAML text and validate all required fields are present."""
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"GPT output is not valid YAML:\n{e}\n\nRaw:\n{yaml_text}")

    # GPT sometimes returns a list with one item, sometimes a bare dict
    if isinstance(parsed, list):
        if not parsed:
            raise ValueError("GPT returned an empty YAML list.")
        scenario = parsed[0]
    elif isinstance(parsed, dict):
        scenario = parsed
    else:
        raise ValueError(f"Unexpected YAML type: {type(parsed)}")

    required = {"id", "name", "dob", "condition", "goal", "personality",
                "tts_voice", "max_turns", "system_prompt"}
    missing = required - set(scenario.keys())
    if missing:
        raise ValueError(f"Generated scenario missing required fields: {missing}")

    # Validate voice
    valid_voices = {"nova", "onyx", "shimmer"}
    if scenario["tts_voice"] not in valid_voices:
        log.warning(
            f"Generated tts_voice '{scenario['tts_voice']}' is not standard. "
            f"Defaulting to 'nova'."
        )
        scenario["tts_voice"] = "nova"

    # Validate id is not a duplicate
    if PATIENTS_YAML.exists():
        with open(PATIENTS_YAML, encoding="utf-8") as f:
            existing = yaml.safe_load(f)
        existing_ids = {s["id"] for s in existing.get("scenarios", [])}
        if scenario["id"] in existing_ids:
            scenario["id"] = f"{scenario['id']}_v2"
            log.warning(f"Duplicate ID detected — renamed to {scenario['id']}")

    return scenario


def save_scenario(scenario: dict, output_path: Path) -> None:
    """Write one scenario to a YAML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            [scenario],
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    log.info(f"Saved: {output_path}")


def append_to_patients_yaml(scenario: dict) -> None:
    """Append a new scenario to scenarios/patients.yaml."""
    with open(PATIENTS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["scenarios"].append(scenario)
    with open(PATIENTS_YAML, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    log.info(f"Appended '{scenario['id']}' to {PATIENTS_YAML}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate GPT-4o patient scenarios targeting known PGAI bugs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_scenarios.py --preset confirmation_bypass
  python generate_scenarios.py --preset emergency_retry --dry-run
  python generate_scenarios.py --preset session_contamination --append
  python generate_scenarios.py --condition "back pain" --age 40 --urgency low --frustration low --bugs H3,H4
  python generate_scenarios.py --batch --bugs C1,C2 --count 2
  python generate_scenarios.py --list-presets
        """,
    )
    parser.add_argument("--preset", choices=list(PRESETS.keys()), help="Use a bug-targeted preset")
    parser.add_argument("--condition", help="Patient medical condition")
    parser.add_argument("--age", type=int, help="Patient age")
    parser.add_argument("--urgency", choices=["low", "medium", "high", "critical"], default="medium")
    parser.add_argument("--frustration", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--bugs", help="Comma-separated bug IDs to target, e.g. C1,H3")
    parser.add_argument("--count", type=int, default=1, help="Number of scenarios to generate (batch mode)")
    parser.add_argument("--batch", action="store_true", help="Generate --count scenarios for the given bugs")
    parser.add_argument("--append", action="store_true", help="Append generated scenario(s) to patients.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print scenario but do not save")
    parser.add_argument("--list-presets", action="store_true", help="List available presets and exit")
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model (default: gpt-4o)")
    args = parser.parse_args()

    if args.list_presets:
        print("\nAvailable presets:\n")
        for name, cfg in PRESETS.items():
            bugs = ", ".join(cfg["bugs"])
            print(f"  {name:<30} → targets {bugs}")
            print(f"    condition: {cfg['condition']}")
            print()
        return

    # Build generation parameters
    if args.preset:
        cfg = PRESETS[args.preset]
        condition    = cfg["condition"]
        age          = cfg["age"]
        urgency      = cfg["urgency"]
        frustration  = cfg["frustration"]
        bugs         = cfg["bugs"]
        hint         = cfg.get("scenario_hint", "")
        base_name    = args.preset
    elif args.condition and args.age and args.bugs:
        condition   = args.condition
        age         = args.age
        urgency     = args.urgency
        frustration = args.frustration
        bugs        = [b.strip() for b in args.bugs.split(",")]
        hint        = ""
        base_name   = "_".join(bugs).lower()
    else:
        parser.error(
            "Specify --preset or all of: --condition, --age, --bugs\n"
            "Run with --list-presets to see available presets."
        )
        return

    count = args.count if args.batch else 1
    generated = []

    for i in range(count):
        suffix = f"_v{i+1}" if count > 1 else ""
        log.info(f"Generating scenario {i+1}/{count} for bugs: {', '.join(bugs)}")
        try:
            scenario = generate_scenario(
                condition=condition,
                age=age,
                urgency=urgency,
                frustration=frustration,
                bugs=bugs,
                scenario_hint=hint,
                model=args.model,
            )
            generated.append(scenario)
            log.info(f"Generated: id={scenario['id']}, name={scenario['name']}, voice={scenario['tts_voice']}")
        except Exception as e:
            log.error(f"Generation {i+1} failed: {e}")
            continue

    if not generated:
        log.error("No scenarios were generated.")
        sys.exit(1)

    for scenario in generated:
        yaml_output = yaml.dump(
            [scenario],
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

        if args.dry_run:
            print("\n" + "=" * 60)
            print(f"[DRY RUN] Generated scenario: {scenario['id']}")
            print("=" * 60)
            print(yaml_output)
        else:
            out_path = GENERATED_DIR / f"{scenario['id']}.yaml"
            save_scenario(scenario, out_path)

            if args.append:
                append_to_patients_yaml(scenario)

    if not args.dry_run:
        print(f"\n✓ Generated {len(generated)} scenario(s) in {GENERATED_DIR}/")
        if args.append:
            print(f"✓ Appended to {PATIENTS_YAML}")
        print("\nRun with run_scenario.py --scenario <id> to test the new scenario.")


if __name__ == "__main__":
    main()
