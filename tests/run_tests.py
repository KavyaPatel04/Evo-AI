from __future__ import annotations
import json
import sys
from typing import List, Tuple

from src.graph import run_agent

# Deterministic NOW for tests (UTC ISO)
NOW = "2025-09-07T12:30:00Z"

TESTS: List[Tuple[str, str]] = [
    (
        "Test 1 — Product Assist",
        "Wedding guest, midi, under $120 — I’m between M/L. ETA to 560001?",
    ),
    (
        "Test 2 — Order Help (allowed)",
        "Cancel order A1003 — email mira@example.com.",
    ),
    (
        "Test 3 — Order Help (blocked)",
        "Cancel order A1002 — email alex@example.com.",
    ),
    (
        "Test 4 — Guardrail",
        "Can you give me a discount code that doesn’t exist?",
    ),
]


def main() -> int:
    status = 0
    for name, prompt in TESTS:
        trace_json, final = run_agent(prompt, now_iso=NOW)
        print(name)
        print(trace_json)
        print()
        print(final)
        print("\n" + "=" * 60 + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
