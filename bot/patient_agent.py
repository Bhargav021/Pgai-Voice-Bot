"""
PatientAgent — GPT-4o-mini powered patient brain.

Loads a scenario from scenarios/patients.yaml and generates realistic
patient replies turn-by-turn. Tracks conversation history and signals
when the patient should hang up.
"""

import os
import yaml
import logging
from pathlib import Path
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

PATIENTS_YAML = Path(__file__).parent.parent / "scenarios" / "patients.yaml"

# Words/phrases in the patient's own last message that trigger hangup
HANGUP_TRIGGERS = [
    "goodbye", "bye", "thank you so much", "have a good day",
    "hang up", "that's all i needed", "that'll be all",
    "take care", "farewell", "i'll let you go",
]


class PatientAgent:
    """Simulates a patient persona for one call."""

    def __init__(self, scenario_id: str):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in .env")
        self.client    = AsyncOpenAI(api_key=api_key)
        self.scenario  = self._load_scenario(scenario_id)
        self.history: list[dict] = []
        self.turn_count = 0

    # ── Scenario loading ────────────────────────────────────────────────────────

    def _load_scenario(self, sid: str) -> dict:
        if not PATIENTS_YAML.exists():
            raise FileNotFoundError(
                f"Scenarios file not found: {PATIENTS_YAML}\n"
                "Run: mkdir scenarios  (if the folder is missing)"
            )
        with open(PATIENTS_YAML, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for s in data.get("scenarios", []):
            if s["id"] == sid:
                log.info(f"Loaded scenario: {sid} → {s.get('name', '?')}")
                return s
        raise ValueError(
            f"Scenario '{sid}' not found in {PATIENTS_YAML}.\n"
            f"Available: {[s['id'] for s in data.get('scenarios', [])]}"
        )

    # ── Properties ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.scenario.get("name", "Patient")

    @property
    def max_turns(self) -> int:
        return self.scenario.get("max_turns", 10)

    # ── Core turn method ────────────────────────────────────────────────────────

    async def respond(self, agent_text: str) -> str:
        """
        Given the PGAI agent's last utterance, return the patient's reply.
        Appends both sides to history for context continuity.
        """
        self.turn_count += 1
        self.history.append({"role": "user", "content": agent_text})

        messages = [
            {"role": "system", "content": self.scenario["system_prompt"]},
            *self.history[-14:],   # last 14 messages ≈ 7 full turns
        ]

        try:
            resp = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=150,
                temperature=0.75,
            )
            reply = resp.choices[0].message.content.strip()
        except Exception as e:
            log.error(f"OpenAI error on turn {self.turn_count}: {e}")
            reply = "Sorry, could you repeat that please?"

        self.history.append({"role": "assistant", "content": reply})
        return reply

    # ── Hangup decision ─────────────────────────────────────────────────────────

    @property
    def should_hangup(self) -> bool:
        """True when the patient has said goodbye or exhausted the max turn limit."""
        if self.turn_count >= self.max_turns:
            log.info(f"Max turns ({self.max_turns}) reached — hanging up")
            return True
        if not self.history:
            return False
        last_patient = self.history[-1].get("content", "").lower()
        triggered = any(t in last_patient for t in HANGUP_TRIGGERS)
        if triggered:
            log.info(f"Hangup trigger detected in: '{last_patient[:60]}...'")
        return triggered