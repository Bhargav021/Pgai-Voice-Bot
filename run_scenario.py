"""
run_scenario.py — scenario runner CLI.
Run one scenario, repeat a scenario, or run all 12 scenarios sequentially.

Usage:
    python run_scenario.py --scenario simple_scheduling
    python run_scenario.py --scenario medication_refill --count 2
    python run_scenario.py --all
    python run_scenario.py --list
"""

import time
import argparse
import logging

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_scenario")

# All 12 scenario IDs — must match ids in scenarios/patients.yaml
ALL_SCENARIOS = [
    # Core scenarios (6)
    "simple_scheduling",
    "rescheduling",
    "cancellation",
    "medication_refill",
    "office_hours",
    "insurance_query",
    # Edge case scenarios (6)
    "weekend_appointment",
    "angry_patient",
    "barge_in_test",
    "multiple_requests",
    "unclear_speech",
    "emergency_escalation",
]

# Minimum gap between calls — be respectful of the test line
CALL_GAP_SECONDS = 180   # 3 minutes; reduce to 60 for quick debugging


def run_scenario(scenario_id: str, call_number: int = 1) -> str:
    from run_call import place_call
    log.info("=" * 60)
    log.info(f"Call #{call_number}: {scenario_id}")
    log.info("=" * 60)
    sid = place_call(scenario=scenario_id)
    return sid


def main():
    parser = argparse.ArgumentParser(
        description="Run PGAI patient simulation scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scenario.py --scenario simple_scheduling
  python run_scenario.py --scenario medication_refill --count 2
  python run_scenario.py --all --gap 120
  python run_scenario.py --list
        """,
    )
    parser.add_argument(
        "--scenario", choices=ALL_SCENARIOS,
        help="Single scenario ID to run"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Run all 12 scenarios sequentially"
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="How many times to run the selected scenario (default: 1)"
    )
    parser.add_argument(
        "--gap", type=int, default=CALL_GAP_SECONDS,
        help=f"Seconds to wait between calls (default: {CALL_GAP_SECONDS})"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all available scenarios and exit"
    )
    args = parser.parse_args()

    if args.list:
        print("\nAvailable scenarios:")
        for i, s in enumerate(ALL_SCENARIOS, 1):
            category = "edge" if i > 6 else "core"
            print(f"  {i:2d}. {s:<30} [{category}]")
        return

    if not args.scenario and not args.all:
        parser.error("Specify --scenario <id>, --all, or --list")

    # Build the call queue
    if args.all:
        queue = ALL_SCENARIOS
    else:
        queue = [args.scenario] * args.count

    results = []
    for i, scenario_id in enumerate(queue, 1):
        sid = run_scenario(scenario_id, i)
        results.append((scenario_id, sid))

        # Wait between calls (except after the last one)
        if i < len(queue):
            log.info(f"Waiting {args.gap}s before next call... (Ctrl+C to abort)")
            try:
                time.sleep(args.gap)
            except KeyboardInterrupt:
                log.info("Interrupted — stopping after this call.")
                break

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Completed {len(results)} call(s):")
    for scenario_id, sid in results:
        print(f"  {scenario_id:<30} -> {sid}")
    print(f"{'=' * 60}")
    print("Check recordings/ and transcripts/ for outputs.")


if __name__ == "__main__":
    main()