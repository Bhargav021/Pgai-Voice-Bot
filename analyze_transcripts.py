"""
analyze_transcripts.py  — Post-call bug analysis using GPT-4o.

Reads every transcript in transcripts/ and uses GPT-4o to:
  1. Summarise the conversation
  2. Identify bugs / unexpected behaviours in the PGAI agent
  3. Score severity (Critical / High / Medium / Low)

Outputs:
  - Console summary per transcript
  - BUG_REPORT.md — consolidated markdown bug report
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

TRANSCRIPT_DIR = Path("transcripts")
OUTPUT_FILE    = Path("BUG_REPORT.md")

# ── Severity levels ───────────────────────────────────────────────────────────
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


ANALYSIS_PROMPT = """You are a QA engineer reviewing a test call made to an AI medical receptionist.
The transcript below shows an automated patient simulator (PATIENT) talking to the AI receptionist (AGENT).

Your job:
1. Identify every bug, failure, or unexpected behaviour from the AGENT.
2. For each bug assign a severity: Critical | High | Medium | Low.
3. Give each bug a short title (≤10 words) and a 1-2 sentence description.
4. Note the transcript line(s) where the bug occurs.

Reply in this exact format — one block per bug:

BUG: <short title>
SEVERITY: <Critical|High|Medium|Low>
LINES: <line numbers, e.g. 3, 7>
DESCRIPTION: <1-2 sentences>
---

If no bugs found, reply: NO_BUGS
"""


def read_transcript(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def analyze(transcript_text: str, label: str) -> list[dict]:
    """Call GPT-4o to analyse a transcript. Returns list of bug dicts."""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": ANALYSIS_PROMPT},
            {"role": "user",   "content": f"TRANSCRIPT ({label}):\n\n{transcript_text}"},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()

    if raw.strip() == "NO_BUGS":
        return []

    bugs = []
    for block in raw.split("---"):
        block = block.strip()
        if not block:
            continue
        bug = {}
        for line in block.splitlines():
            if line.startswith("BUG:"):
                bug["title"] = line[4:].strip()
            elif line.startswith("SEVERITY:"):
                bug["severity"] = line[9:].strip()
            elif line.startswith("LINES:"):
                bug["lines"] = line[6:].strip()
            elif line.startswith("DESCRIPTION:"):
                bug["description"] = line[12:].strip()
        if "title" in bug and "severity" in bug:
            bug.setdefault("lines", "—")
            bug.setdefault("description", "")
            bug["source"] = label
            bugs.append(bug)

    return bugs


def main():
    transcripts = sorted(TRANSCRIPT_DIR.glob("*.txt"))
    if not transcripts:
        print("No transcripts found in transcripts/")
        return

    print(f"Analysing {len(transcripts)} transcript(s)...\n")

    all_bugs: list[dict] = []

    for path in transcripts:
        label = path.stem
        text  = read_transcript(path)
        turns = [l for l in text.splitlines() if l.startswith("AGENT:") or l.startswith("PATIENT:")]
        if len(turns) < 2:
            print(f"  SKIP  {label}  (only {len(turns)} turn(s) — too short to analyse)")
            continue

        print(f"  -> {label}  ({len(turns)} turns)", end="  ", flush=True)
        bugs = analyze(text, label)
        print(f"{len(bugs)} bug(s) found")
        all_bugs.extend(bugs)

    # ── Deduplicate bugs by title (keep highest-severity instance) ───────────
    seen: dict[str, dict] = {}
    for bug in all_bugs:
        key = bug["title"].lower()
        if key not in seen:
            seen[key] = bug
        else:
            existing_sev = SEVERITY_ORDER.get(seen[key]["severity"], 99)
            new_sev      = SEVERITY_ORDER.get(bug["severity"], 99)
            if new_sev < existing_sev:
                seen[key] = bug
            else:
                # Append source
                seen[key]["source"] += f", {bug['source']}"

    unique_bugs = sorted(seen.values(), key=lambda b: SEVERITY_ORDER.get(b["severity"], 99))

    # ── Write BUG_REPORT.md ──────────────────────────────────────────────────
    lines = [
        "# PGAI Voice Bot — Bug Report",
        "",
        f"**Total unique bugs found:** {len(unique_bugs)}  ",
        f"**Transcripts analysed:** {len(transcripts)}  ",
        f"**Scenarios tested:** {len(set(p.stem.rsplit('-', 2)[0] for p in transcripts))}  ",
        "",
        "---",
        "",
    ]

    for sev in ["Critical", "High", "Medium", "Low"]:
        sev_bugs = [b for b in unique_bugs if b.get("severity") == sev]
        if not sev_bugs:
            continue
        lines.append(f"## {sev} ({len(sev_bugs)})")
        lines.append("")
        for i, bug in enumerate(sev_bugs, 1):
            lines.append(f"### {sev[0]}{i}. {bug['title']}")
            lines.append(f"- **Severity:** {bug['severity']}")
            lines.append(f"- **Found in:** `{bug['source']}`")
            lines.append(f"- **Lines:** {bug['lines']}")
            lines.append(f"- **Description:** {bug['description']}")
            lines.append("")

    lines += [
        "---",
        "",
        "## How Bugs Were Found",
        "",
        "An automated Python bot placed 12 outbound calls to the PGAI AI receptionist at +1-805-439-8008.",
        "Each call used a different patient persona and scenario (scheduling, cancellation, medication refill,",
        "emergency escalation, etc.). Calls were transcribed in real time using Deepgram Nova-2 STT,",
        "and patient responses were generated by GPT-4o-mini. This file was produced by GPT-4o analysing",
        "the saved transcripts.",
        "",
    ]

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nBug report saved -> {OUTPUT_FILE}  ({len(unique_bugs)} unique bugs)")

    # Console summary
    print("\n" + "=" * 60)
    print("BUG SUMMARY")
    print("=" * 60)
    for sev in ["Critical", "High", "Medium", "Low"]:
        sev_bugs = [b for b in unique_bugs if b.get("severity") == sev]
        if sev_bugs:
            print(f"\n{sev}:")
            for b in sev_bugs:
                print(f"  • {b['title']}")


if __name__ == "__main__":
    main()