"""
analyze_transcripts.py — GPT-4o structured test oracle for PGAI call transcripts.

Analyzes each transcript and produces a machine-readable JSON verdict:
  - goal_achieved: did the patient accomplish their scenario objective?
  - bugs_found: list with severity, line number, and verbatim evidence
  - pgai_behaviors: observed agent behaviors for cross-call pattern analysis
  - conversation_quality: turn count, fragmented turns, disclaimer waste, etc.

All results are saved to analysis_results/ as individual JSON files plus a
combined analysis_summary.json. The original BUG_REPORT.md output is also
preserved for backwards compatibility.

Usage:
    python analyze_transcripts.py                        # analyze all transcripts
    python analyze_transcripts.py --transcript transcripts/emergency_escalation-20260623-161659.txt
    python analyze_transcripts.py --summary              # print summary of existing results
    python analyze_transcripts.py --output analysis_results/
    python analyze_transcripts.py --model gpt-4o-mini    # faster/cheaper
    python analyze_transcripts.py --reanalyze            # force re-analyze even if verdict exists
"""

import os
import re
import sys
import json
import yaml
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 output on Windows (avoids CP1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analyze_transcripts")

PATIENTS_YAML   = Path("scenarios/patients.yaml")
TRANSCRIPTS_DIR = Path("transcripts")
OUTPUT_DIR      = Path("analysis_results")

# ── Known bugs — injected as context so GPT knows what to look for ───────────

KNOWN_BUGS = {
    "C1": "No confirmation number provided after booking appointment",
    "C2": "Cross-patient data exposed — different caller's appointment details shown (HIPAA)",
    "C3": "Transfer endpoint immediately disconnects caller ('Pretty Good AI test line. Goodbye')",
    "C4": "Identity verification bypassed with 'for demo purposes I'll accept it'",
    "C5": "Emergency 911 advice truncated mid-sentence — words 'call 911' never delivered",
    "H1": "Agent falsely reports patient already has an appointment that doesn't exist",
    "H2": "Agent auto-assigns wrong date of birth (e.g. 07/04/2000) without asking patient",
    "H3": "Agent defers booking to support team instead of confirming appointment directly",
    "H4": "Conversation resets to 'How can I help you?' after profile creation, losing context",
    "H5": "Agent blocks medication refill when patient declines to provide phone number",
    "H6": "Agent asks for name+DOB 3 times in circular verification loop before failing",
    "H7": "Agent addresses new caller by previous caller's name (cross-session contamination)",
    "H8": "Agent claims equal authority to supervisor, refuses escalation",
    "H9": "2-turn delay before recognising cardiac emergency — agent completes greeting first",
    "M1": "Agent routes patient to wrong specialty (orthopedics for diabetes/non-ortho conditions)",
    "M2": "Truncated/fragmented agent utterances (missing beginning or end of sentence)",
    "M3": "Sentence starts with 'But' without preceding clause (clipped TTS response)",
    "M4": "No explicit cancellation confirmation message provided",
    "M5": "Doctor name unintelligible in TTS (non-English name mispronounced)",
    "M6": "Practice name inconsistent between calls",
    "M7": "Agent ignores patient question then answers only after patient repeats it",
    "M8": "Truncated closing utterance (e.g. 'Me know if you have any questions')",
    "M9": "Agent requires identity verification for publicly available information",
    "M10": "Agent confirms wrong day-of-week, self-contradicts within same call",
    "L1": "Agent narrates internal state aloud ('I am processing your request')",
}

# ── JSON schema shown to GPT-4o so it knows what structure to return ─────────

VERDICT_SCHEMA = """{
  "scenario":        "string — scenario ID extracted from filename",
  "transcript_file": "string — filename",
  "call_label":      "string — value of the 'Call:' header line",
  "goal_achieved":   true | false,
  "goal_summary":    "string — 1 sentence: what the patient wanted and whether they got it",
  "bugs_found": [
    {
      "id":        "string — e.g. 'C1' or 'NEW' for unlisted bugs",
      "severity":  "critical | high | medium | low",
      "line":      integer,
      "evidence":  "string — verbatim agent quote or brief description",
      "new_title": "string — only present when id is 'NEW'"
    }
  ],
  "pgai_behaviors": ["string — short observed behavior, e.g. 'asked_for_phone_number: true'"],
  "conversation_quality": {
    "total_turns":         integer,
    "agent_turns":         integer,
    "patient_turns":       integer,
    "disclaimer_response": true | false,
    "fragmented_turns":    integer,
    "emergency_detected":  true | false,
    "emergency_handled":   true | false,
    "max_turn_reached":    true | false
  },
  "summary": "string — 2-3 sentence human-readable summary of the call and key findings"
}"""


# ── Transcript parsing ────────────────────────────────────────────────────────

def _parse_transcript(path: Path) -> tuple[str, list[tuple[int, str, str]]]:
    """Returns (call_label, [(lineno, speaker, text), ...])."""
    call_label = ""
    turns: list[tuple[int, str, str]] = []
    with open(path, encoding="utf-8") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if line.startswith("Call:"):
                call_label = line.replace("Call:", "").strip()
            elif line.startswith("AGENT:"):
                turns.append((i, "AGENT", line[6:].strip()))
            elif line.startswith("PATIENT:"):
                turns.append((i, "PATIENT", line[8:].strip()))
    return call_label, turns


def _scenario_from_filename(fname: str) -> str:
    return fname.rsplit("-", 2)[0] if fname.count("-") >= 2 else fname.replace(".txt", "")


def _load_scenario_goal(scenario_id: str) -> str:
    if not PATIENTS_YAML.exists():
        return "Not available"
    with open(PATIENTS_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for s in data.get("scenarios", []):
        if s["id"] == scenario_id:
            return s.get("goal", "Not specified")
    return "Not found in patients.yaml"


def _quick_quality_metrics(turns: list[tuple[int, str, str]]) -> dict:
    """Derive quality metrics from raw turns without any API call."""
    DISCLAIMER = re.compile(r"recorded for quality|quality and training|this call may be recorded", re.I)
    FRAGMENT   = re.compile(r"^(but |and |or |so |then |also |just |now |well )", re.I)
    EMERGENCY  = re.compile(r"\b(chest|911|cardiac|stroke|heart attack|left arm|can.t breathe|unconscious)\b", re.I)
    GOODBYE    = re.compile(r"\b(goodbye|bye|call back|act on this now)\b", re.I)

    agent_turns   = [(n, s, t) for n, s, t in turns if s == "AGENT"]
    patient_turns = [(n, s, t) for n, s, t in turns if s == "PATIENT"]

    # Disclaimer waste: patient's first response looks like acknowledging disclaimer
    disclaimer_response = False
    if agent_turns and patient_turns:
        first_agent = agent_turns[0][2].lower()
        first_patient = patient_turns[0][2].lower() if patient_turns else ""
        if DISCLAIMER.search(first_agent):
            disclaimer_response = any(
                w in first_patient for w in ("fine", "understand", "okay", "ok", "sure", "of course")
            )

    fragmented = sum(
        1 for _, _, t in agent_turns
        if FRAGMENT.match(t) or (t and t[0].islower())
    )

    all_text = " ".join(t for _, _, t in turns)
    emergency_detected = bool(EMERGENCY.search(all_text))
    emergency_handled  = bool(re.search(r"\b911\b", all_text)) if emergency_detected else False

    last_patient = patient_turns[-1][2] if patient_turns else ""
    max_turn_reached = bool(GOODBYE.search(last_patient))

    return {
        "total_turns":         len(turns),
        "agent_turns":         len(agent_turns),
        "patient_turns":       len(patient_turns),
        "disclaimer_response": disclaimer_response,
        "fragmented_turns":    fragmented,
        "emergency_detected":  emergency_detected,
        "emergency_handled":   emergency_handled,
        "max_turn_reached":    max_turn_reached,
    }


# ── GPT-4o analysis ──────────────────────────────────────────────────────────

def _build_prompt(
    transcript_text: str,
    scenario_id: str,
    scenario_goal: str,
    call_label: str,
    quick_metrics: dict,
) -> str:
    bugs_list = "\n".join(f"  {k}: {v}" for k, v in KNOWN_BUGS.items())
    return f"""You are a QA engineer analyzing a test call to an AI medical receptionist.

SCENARIO:      {scenario_id}
CALL LABEL:    {call_label}
PATIENT GOAL:  {scenario_goal}

PRE-COMPUTED METRICS (use to populate conversation_quality — override if you disagree):
{json.dumps(quick_metrics, indent=2)}

KNOWN BUGS IN THIS SYSTEM (reference these IDs in bugs_found when applicable):
{bugs_list}

TRANSCRIPT (L=line number):
{transcript_text}

INSTRUCTIONS:
1. Check the transcript for EVERY known bug in the list above AND any new ones not listed.
2. For each bug: pick the exact line where the evidence is clearest and quote the agent verbatim.
3. New bugs get id="NEW" and must include a new_title field.
4. goal_achieved = true only if the patient clearly accomplished their stated goal before hanging up.
5. pgai_behaviors: short boolean-style strings describing observed agent actions.
6. disclaimer_response = true if the patient bot wasted a turn responding to the privacy disclaimer.
7. fragmented_turns = count of agent turns that start mid-sentence (lowercase first word, or starts with But/And/Or).

OUTPUT: valid JSON ONLY — no markdown, no explanation, no text before or after the JSON.

TARGET SCHEMA:
{VERDICT_SCHEMA}"""


def analyze_transcript(path: Path, model: str = "gpt-4o") -> dict[str, Any]:
    """Analyze one transcript. Returns structured verdict dict."""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    call_label, turns = _parse_transcript(path)
    scenario_id   = _scenario_from_filename(path.name)
    scenario_goal = _load_scenario_goal(scenario_id)
    quick_metrics = _quick_quality_metrics(turns)

    transcript_lines = [f"L{n:02d} {s}: {t}" for n, s, t in turns]
    transcript_text  = "\n".join(transcript_lines)

    prompt = _build_prompt(transcript_text, scenario_id, scenario_goal, call_label, quick_metrics)

    for attempt in range(1, 4):
        try:
            log.info(f"  GPT-4o analyzing {path.name}  (attempt {attempt})")
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1600,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            verdict = json.loads(raw)

            # Guarantee required fields
            verdict.setdefault("scenario",        scenario_id)
            verdict.setdefault("transcript_file", path.name)
            verdict.setdefault("call_label",      call_label)
            verdict.setdefault("conversation_quality", quick_metrics)
            verdict["_analyzed_at"] = datetime.now().isoformat()
            verdict["_model"]       = model
            return verdict

        except json.JSONDecodeError as e:
            log.warning(f"  JSON parse error attempt {attempt}: {e}")
        except Exception as e:
            log.error(f"  API error attempt {attempt}: {e}")
            if attempt < 3:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Analysis failed for {path.name}")


# ── Cross-call summary ────────────────────────────────────────────────────────

def _build_summary(verdicts: list[dict]) -> dict:
    total  = len(verdicts)
    passed = sum(1 for v in verdicts if v.get("goal_achieved", False))

    bug_freq: dict[str, dict] = {}
    for v in verdicts:
        for b in v.get("bugs_found", []):
            bid = b.get("id", "?")
            if bid not in bug_freq:
                bug_freq[bid] = {
                    "count": 0,
                    "severity": b.get("severity", "?"),
                    "description": KNOWN_BUGS.get(bid, b.get("new_title", "unlisted")),
                    "calls": [],
                }
            bug_freq[bid]["count"] += 1
            bug_freq[bid]["calls"].append(v.get("scenario", "?"))

    qm = [v.get("conversation_quality", {}) for v in verdicts]
    avg_turns = round(sum(q.get("total_turns", 0) for q in qm) / total, 1) if total else 0
    avg_frags = round(sum(q.get("fragmented_turns", 0) for q in qm) / total, 1) if total else 0
    disc_waste = sum(1 for q in qm if q.get("disclaimer_response", False))

    emerg = [v for v in verdicts if v.get("conversation_quality", {}).get("emergency_detected")]
    emerg_ok = sum(1 for v in emerg if v.get("conversation_quality", {}).get("emergency_handled"))

    sorted_bugs = sorted(bug_freq.items(), key=lambda x: -x[1]["count"])

    return {
        "generated_at":             datetime.now().isoformat(),
        "total_calls_analyzed":     total,
        "goals_achieved":           passed,
        "goals_failed":             total - passed,
        "goal_success_rate":        round(passed / total, 2) if total else 0,
        "unique_bugs_found":        len(bug_freq),
        "total_bug_instances":      sum(b["count"] for b in bug_freq.values()),
        "bug_frequency":            dict(sorted_bugs),
        "avg_turns_per_call":       avg_turns,
        "avg_fragmented_turns":     avg_frags,
        "disclaimer_waste_calls":   disc_waste,
        "emergency_calls":          len(emerg),
        "emergency_handled":        emerg_ok,
        "emergency_handle_rate":    round(emerg_ok / len(emerg), 2) if emerg else None,
        "critical_bugs":            [bid for bid, b in bug_freq.items() if b["severity"] == "critical"],
    }


# ── Reporting ─────────────────────────────────────────────────────────────────

def _print_verdict_brief(v: dict) -> None:
    goal_str = "ACHIEVED" if v.get("goal_achieved") else "NOT ACHIEVED"
    bugs = v.get("bugs_found", [])
    crit = sum(1 for b in bugs if b.get("severity") == "critical")
    qual = v.get("conversation_quality", {})
    print(f"\n  {v.get('scenario','?'):<30}  goal={goal_str}  bugs={len(bugs)}({crit}crit)  turns={qual.get('total_turns','?')}")
    if v.get("summary"):
        print(f"    {v['summary'][:115]}")
    for b in bugs[:3]:
        print(f"    [{b.get('severity','?').upper()[:4]}] {b.get('id','?')}: {b.get('evidence','')[:70]}")
    if len(bugs) > 3:
        print(f"    ... +{len(bugs)-3} more bugs")


def _print_summary_report(s: dict) -> None:
    print("\n" + "=" * 65)
    print("PGAI TEST ORACLE — ANALYSIS SUMMARY")
    print(f"Generated: {s['generated_at'][:19]}")
    print("=" * 65)
    print(f"Calls analyzed    : {s['total_calls_analyzed']}")
    print(f"Goals achieved    : {s['goals_achieved']} / {s['total_calls_analyzed']} ({s['goal_success_rate']*100:.0f}%)")
    print(f"Unique bugs found : {s['unique_bugs_found']}")
    print(f"Total bug events  : {s['total_bug_instances']}")
    print(f"Avg turns/call    : {s['avg_turns_per_call']}")
    print(f"Disclaimer waste  : {s['disclaimer_waste_calls']} calls")
    if s["emergency_calls"]:
        rate = (s["emergency_handle_rate"] or 0) * 100
        print(f"Emergency calls   : {s['emergency_calls']} — handled: {s['emergency_handled']} ({rate:.0f}%)")
    print(f"\nCritical bugs: {', '.join(s['critical_bugs']) or 'None'}")
    print("\nTop bugs by frequency:")
    for bid, info in list(s["bug_frequency"].items())[:12]:
        desc = info.get("description", KNOWN_BUGS.get(bid, ""))[:55]
        print(f"  {bid:<5} ×{info['count']}  [{info['severity'].upper()[:4]}]  {desc}")


# ── Legacy BUG_REPORT.md writer (backwards compat) ───────────────────────────

def _write_bug_report_md(verdicts: list[dict], output_path: Path = Path("BUG_REPORT.md")) -> None:
    """Write a markdown bug report from structured verdicts (upgrades old format)."""
    all_bugs: list[dict] = []
    for v in verdicts:
        for b in v.get("bugs_found", []):
            b["_scenario"] = v.get("scenario", "?")
            b["_file"]     = v.get("transcript_file", "?")
            all_bugs.append(b)

    SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_bugs.sort(key=lambda b: SEV_ORDER.get(b.get("severity", "low"), 99))

    lines = [
        "# PGAI Voice Bot — Bug Report (Auto-generated)",
        "",
        f"**Total bug instances:** {len(all_bugs)}  ",
        f"**Transcripts analyzed:** {len(verdicts)}  ",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  ",
        "",
        "> This report is auto-generated from structured verdicts in `analysis_results/`.",
        "> See `analysis_results/analysis_summary.json` for aggregated statistics.",
        "",
        "---",
        "",
    ]

    for sev_label in ["Critical", "High", "Medium", "Low"]:
        sev = sev_label.lower()
        sev_bugs = [b for b in all_bugs if b.get("severity", "").lower() == sev]
        if not sev_bugs:
            continue
        lines.append(f"## {sev_label} ({len(sev_bugs)})")
        lines.append("")
        for i, b in enumerate(sev_bugs, 1):
            bid = b.get("id", "?")
            title = KNOWN_BUGS.get(bid, b.get("new_title", b.get("evidence", "Unknown")[:60]))
            lines += [
                f"### {sev_label[0]}{i}. {title}",
                f"- **Bug ID:** {bid}",
                f"- **Severity:** {sev_label}",
                f"- **Found in:** `{b.get('_file', '?')}`",
                f"- **Line:** {b.get('line', '—')}",
                f"- **Evidence:** {b.get('evidence', '—')}",
                "",
            ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"BUG_REPORT.md updated → {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Structured GPT-4o analysis of PGAI call transcripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze_transcripts.py
  python analyze_transcripts.py --summary
  python analyze_transcripts.py --transcript transcripts/emergency_escalation-20260623-161659.txt
  python analyze_transcripts.py --model gpt-4o-mini
  python analyze_transcripts.py --reanalyze
        """,
    )
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--transcripts-dir", type=Path, default=TRANSCRIPTS_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--summary", action="store_true", help="Print summary of existing results")
    parser.add_argument("--reanalyze", action="store_true", help="Re-analyze even if verdict exists")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between API calls")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    # ── Summary-only ─────────────────────────────────────────────────────────
    if args.summary:
        summary_path = args.output / "analysis_summary.json"
        if summary_path.exists():
            with open(summary_path, encoding="utf-8") as f:
                _print_summary_report(json.load(f))
        else:
            existing = [p for p in args.output.glob("*_verdict.json")]
            if not existing:
                print(f"No verdict files found in {args.output}. Run without --summary first.")
                sys.exit(1)
            verdicts = [json.load(open(p, encoding="utf-8")) for p in existing]
            _print_summary_report(_build_summary(verdicts))
        return

    # ── Select transcripts ────────────────────────────────────────────────────
    paths = [args.transcript] if args.transcript else sorted(args.transcripts_dir.glob("*.txt"))
    if not paths:
        print(f"No transcripts in {args.transcripts_dir}")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set in .env")
        sys.exit(1)

    # ── Analyze ───────────────────────────────────────────────────────────────
    verdicts: list[dict] = []
    for i, path in enumerate(paths):
        result_path = args.output / f"{path.stem}_verdict.json"
        if result_path.exists() and not args.reanalyze:
            with open(result_path, encoding="utf-8") as f:
                verdict = json.load(f)
            log.info(f"  Loaded existing verdict: {path.name}")
            verdicts.append(verdict)
            _print_verdict_brief(verdict)
            continue

        try:
            verdict = analyze_transcript(path, model=args.model)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(verdict, f, indent=2, ensure_ascii=False)
            verdicts.append(verdict)
            _print_verdict_brief(verdict)
            if i < len(paths) - 1:
                time.sleep(args.delay)
        except Exception as e:
            log.error(f"Failed {path.name}: {e}")

    if not verdicts:
        print("No verdicts produced.")
        sys.exit(1)

    # ── Save summary ──────────────────────────────────────────────────────────
    summary = _build_summary(verdicts)
    summary_path = args.output / "analysis_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    _print_summary_report(summary)
    print(f"\n✓ Verdicts:  {args.output}/<scenario>_verdict.json")
    print(f"✓ Summary:   {summary_path}")

    _write_bug_report_md(verdicts)


if __name__ == "__main__":
    main()
