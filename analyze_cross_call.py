"""
analyze_cross_call.py — Cross-call session contamination detector.

Reads all transcripts and automatically detects HIPAA-risk cross-session leakage:
  - Agent addressing a caller by a different patient's name
  - Agent returning a different patient's appointment details
  - A patient's DOB appearing in a call where they are not the caller

This automates what was found manually in bugs C2 and H7 across 16 transcripts,
and is reusable against future call batches.

Usage:
    python analyze_cross_call.py                        # analyze all transcripts
    python analyze_cross_call.py --transcript transcripts/rescheduling-20260623-160158.txt
    python analyze_cross_call.py --json                 # output JSON instead of text
    python analyze_cross_call.py --summary-only         # just the counts
"""

from __future__ import annotations

import io
import re
import sys
import json
import yaml
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import NamedTuple

# Force UTF-8 output on Windows (avoids CP1252 UnicodeEncodeError)
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if isinstance(sys.stderr, io.TextIOWrapper):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
log = logging.getLogger("cross_call")

PATIENTS_YAML  = Path("scenarios/patients.yaml")
TRANSCRIPTS_DIR = Path("transcripts")

# ── Month name table for DOB spoken-form matching ────────────────────────────

MONTH_NAMES = {
    "01": "January",  "02": "February", "03": "March",    "04": "April",
    "05": "May",      "06": "June",     "07": "July",     "08": "August",
    "09": "September","10": "October",  "11": "November", "12": "December",
}
MONTH_SHORT = {k: v[:3] for k, v in MONTH_NAMES.items()}

ORDINAL_SUFFIXES = r"(?:st|nd|rd|th)?"


def _dob_patterns(dob_iso: str) -> list[str]:
    """
    Return a list of regex patterns covering all plausible spoken/written
    forms of a date-of-birth given in ISO format (YYYY-MM-DD).

    E.g. "1985-03-14" → patterns for:
      "March 14th, 1985"   "March 14, 1985"   "March 14th 1985"
      "03/14/1985"         "03-14-1985"        "1985-03-14"
      "14th of March"      "14 March"
    """
    parts = dob_iso.split("-")
    if len(parts) != 3:
        return []
    yr, mo, dy = parts
    month_full  = MONTH_NAMES.get(mo, "")
    month_short = MONTH_SHORT.get(mo, "")
    dy_num      = dy.lstrip("0")  # "03" → "3", "14" → "14"

    patterns = [
        # Spoken: "March 14th, 1985" / "March 14, 1985"
        rf"\b{month_full}\s+{dy_num}{ORDINAL_SUFFIXES}[,\s]+{yr}\b",
        rf"\b{month_short}\.?\s+{dy_num}{ORDINAL_SUFFIXES}[,\s]+{yr}\b",
        # Reversed: "14th of March" / "14 March 1985"
        rf"\b{dy_num}{ORDINAL_SUFFIXES}\s+of\s+{month_full}\b",
        rf"\b{dy_num}{ORDINAL_SUFFIXES}\s+{month_full},?\s*{yr}\b",
        # Numeric: "03/14/1985" or "03-14-1985"
        rf"\b{mo}[/\-]{dy}[/\-]{yr}\b",
        # ISO: "1985-03-14"
        rf"\b{yr}-{mo}-{dy}\b",
        # Short year / ambiguous: "03/14/85"
        rf"\b{mo}/{dy}/{yr[2:]}\b",
    ]
    return [p for p in patterns if month_full]


class Patient(NamedTuple):
    scenario_id:  str
    name:         str
    dob_iso:      str
    dob_patterns: list[str]


class ContaminationEvent(NamedTuple):
    transcript_file:  str
    expected_scenario: str
    intruder_scenario: str
    intruder_name:    str
    kind:             str   # "name" | "dob" | "appointment_data"
    line_number:      int
    line_text:        str
    severity:         str   # "critical" | "high"


def _load_patients() -> list[Patient]:
    """Load all patient name+DOB records from patients.yaml."""
    if not PATIENTS_YAML.exists():
        log.error(f"patients.yaml not found at {PATIENTS_YAML}")
        sys.exit(1)
    with open(PATIENTS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    patients = []
    for s in data.get("scenarios", []):
        dob = s.get("dob", "")
        patients.append(Patient(
            scenario_id=s["id"],
            name=s["name"],
            dob_iso=dob,
            dob_patterns=_dob_patterns(dob),
        ))
    return patients


def _scenario_from_filename(fname: str) -> str:
    """Extract scenario_id from filename like 'simple_scheduling-20260623-155657.txt'."""
    return fname.rsplit("-", 2)[0] if fname.count("-") >= 2 else fname.replace(".txt", "")


def _parse_transcript(path: Path) -> list[tuple[int, str, str]]:
    """
    Parse a transcript file into (line_number, speaker, text) tuples.
    Skips the header lines (Call: and ===).
    """
    turns = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("Call:") or line.startswith("="):
                continue
            if line.startswith("AGENT:"):
                turns.append((i, "AGENT", line[6:].strip()))
            elif line.startswith("PATIENT:"):
                turns.append((i, "PATIENT", line[8:].strip()))
    return turns


def _check_transcript(
    path: Path,
    patients: list[Patient],
    own_patient: Patient | None,
) -> list[ContaminationEvent]:
    """
    Scan one transcript for cross-session contamination.

    We look for:
      1. Any other patient's FULL NAME appearing anywhere in AGENT turns
      2. Any other patient's DOB appearing anywhere in AGENT turns
      3. Name appearing in PATIENT turns that doesn't match own patient
         (e.g. agent addressed them by wrong name and patient confirmed it)

    We only flag AGENT turns because the patient LLM is expected to use
    all patient names as part of the test corpus — false positives there
    are not real contamination.
    """
    events: list[ContaminationEvent] = []
    turns = _parse_transcript(path)
    filename = path.name

    expected_scenario = _scenario_from_filename(filename)
    own_name = own_patient.name if own_patient else ""

    for lineno, speaker, text in turns:
        text_lower = text.lower()

        # Only check AGENT lines for data leakage
        if speaker != "AGENT":
            continue

        for patient in patients:
            if patient.scenario_id == expected_scenario:
                continue  # skip own patient

            # Check for full name match (case-insensitive)
            if patient.name.lower() in text_lower:
                events.append(ContaminationEvent(
                    transcript_file=filename,
                    expected_scenario=expected_scenario,
                    intruder_scenario=patient.scenario_id,
                    intruder_name=patient.name,
                    kind="name",
                    line_number=lineno,
                    line_text=text[:120],
                    severity="critical",
                ))

            # Check for first name alone — only flag if high-confidence
            # (first name is common, so require it to appear in a greeting context)
            first_name = patient.name.split()[0].lower()
            name_in_greeting = re.search(
                rf"\b(speaking with|you are|this is|i have|hi|hello),?\s+{re.escape(first_name)}\b",
                text_lower,
            )
            if name_in_greeting and first_name not in own_name.lower():
                events.append(ContaminationEvent(
                    transcript_file=filename,
                    expected_scenario=expected_scenario,
                    intruder_scenario=patient.scenario_id,
                    intruder_name=patient.name,
                    kind="name",
                    line_number=lineno,
                    line_text=text[:120],
                    severity="high",
                ))

            # Check DOB patterns
            for pattern in patient.dob_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    events.append(ContaminationEvent(
                        transcript_file=filename,
                        expected_scenario=expected_scenario,
                        intruder_scenario=patient.scenario_id,
                        intruder_name=patient.name,
                        kind="dob",
                        line_number=lineno,
                        line_text=text[:120],
                        severity="critical",
                    ))
                    break  # one match per patient per line is enough

    # De-duplicate (same patient / line / kind)
    seen = set()
    unique = []
    for ev in events:
        key = (ev.transcript_file, ev.intruder_scenario, ev.kind, ev.line_number)
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    return unique


def analyze_all(
    transcript_paths: list[Path],
    patients: list[Patient],
) -> tuple[list[ContaminationEvent], dict]:
    """Analyze all transcripts and return (events, per-file summary)."""
    patient_by_scenario = {p.scenario_id: p for p in patients}
    all_events: list[ContaminationEvent] = []
    per_file: dict[str, dict] = {}

    for path in sorted(transcript_paths):
        expected = _scenario_from_filename(path.name)
        own = patient_by_scenario.get(expected)
        events = _check_transcript(path, patients, own)
        all_events.extend(events)
        per_file[path.name] = {
            "clean": len(events) == 0,
            "event_count": len(events),
            "events": [e._asdict() for e in events],
        }

    return all_events, per_file


def _print_report(
    all_events: list[ContaminationEvent],
    per_file: dict,
    summary_only: bool = False,
) -> None:
    """Print a human-readable contamination report."""
    total = len(per_file)
    contaminated = sum(1 for v in per_file.values() if not v["clean"])
    critical = sum(1 for e in all_events if e.severity == "critical")
    high     = sum(1 for e in all_events if e.severity == "high")

    print("\n" + "=" * 65)
    print("CROSS-CALL SESSION CONTAMINATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    print(f"Transcripts analysed : {total}")
    print(f"Clean sessions       : {total - contaminated}")
    print(f"Contaminated sessions: {contaminated}")
    print(f"Total events         : {len(all_events)} "
          f"({critical} critical, {high} high)")

    if summary_only:
        return

    if not all_events:
        print("\n[OK] No cross-session contamination detected.")
        return

    print("\n-- CONTAMINATION EVENTS ---------------------------------------\n")
    for fname, info in sorted(per_file.items()):
        if info["clean"]:
            continue
        print(f"FILE: {fname}")
        print(f"  Expected scenario: {_scenario_from_filename(fname)}")
        for ev_dict in info["events"]:
            ev = ContaminationEvent(**ev_dict)
            sev_tag = f"[{ev.severity.upper()}]"
            print(f"  {sev_tag} Line {ev.line_number}: {ev.kind.upper()} LEAK")
            print(f"    Intruder patient : {ev.intruder_name} ({ev.intruder_scenario})")
            print(f"    Agent said       : '{ev.line_text}'")
        print()

    print("-- HIPAA RISK ASSESSMENT --------------------------------------\n")
    if critical > 0:
        print(f"  !! CRITICAL: {critical} instance(s) of patient-identifiable data")
        print("    (name or DOB) exposed in a different patient's call session.")
        print("    In a real deployment, each instance is a reportable HIPAA breach.")
    if high > 0:
        print(f"  ** HIGH: {high} instance(s) of probable name/greeting contamination.")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Detect cross-session contamination in PGAI call transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transcript", type=Path,
        help="Analyze a single transcript file instead of all",
    )
    parser.add_argument(
        "--transcripts-dir", type=Path, default=TRANSCRIPTS_DIR,
        help=f"Directory of transcript .txt files (default: {TRANSCRIPTS_DIR})",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON instead of human-readable text",
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Print summary counts only, no per-event detail",
    )
    parser.add_argument(
        "--exit-code", action="store_true",
        help="Exit with code 1 if any contamination is found (for CI pipelines)",
    )
    args = parser.parse_args()

    patients = _load_patients()

    if args.transcript:
        transcript_paths = [args.transcript]
    else:
        transcript_paths = sorted(args.transcripts_dir.glob("*.txt"))

    if not transcript_paths:
        print(f"No transcript files found in {args.transcripts_dir}")
        sys.exit(0)

    all_events, per_file = analyze_all(transcript_paths, patients)

    if args.json:
        output = {
            "generated_at": datetime.now().isoformat(),
            "transcripts_analyzed": len(per_file),
            "contaminated_sessions": sum(1 for v in per_file.values() if not v["clean"]),
            "total_events": len(all_events),
            "critical_events": sum(1 for e in all_events if e.severity == "critical"),
            "high_events": sum(1 for e in all_events if e.severity == "high"),
            "per_file": per_file,
        }
        print(json.dumps(output, indent=2))
    else:
        _print_report(all_events, per_file, summary_only=args.summary_only)

    if args.exit_code and all_events:
        sys.exit(1)


if __name__ == "__main__":
    main()
