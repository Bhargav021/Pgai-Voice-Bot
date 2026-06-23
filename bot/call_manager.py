"""
CallManager — per-call state container.

Kept as a simple dataclass so main.py can pass state around cleanly
without a dict. Extend this for multi-call concurrency tracking later.
"""

from dataclasses import dataclass, field


@dataclass
class CallState:
    stream_sid:       str       = ""
    call_sid:         str       = ""
    scenario_id:      str       = ""
    call_label:       str       = ""
    transcript:       list[str] = field(default_factory=list)
    hangup_requested: bool      = False