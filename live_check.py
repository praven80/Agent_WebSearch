"""One live end-to-end run of both options against the configured Gateway.

Costs roughly $0.007 per search plus model tokens. Run it once after deploying to
confirm the whole path works before presenting.

Run:  .venv/bin/python live_check.py
"""

from __future__ import annotations

import sys

from demo.config import load_settings
from demo.modes import MODES

QUESTIONS = [
    "What is the latest stable release of Python, and when did it ship?",
]


def main() -> int:
    settings = load_settings()
    print(f"gateway : {settings.gateway_url}")
    print(f"region  : {settings.gateway_region}")
    print(f"model   : {settings.model_id}")
    print(f"filters : {settings.filters_summary()}")
    print(f"maxResults pinned to {settings.max_results}\n")

    failures = 0
    for question in QUESTIONS:
        print("=" * 78)
        print(f"Q: {question[:90]}")
        for mode in MODES:
            ready, reason = mode.preflight(settings)
            if not ready:
                print(f"  {mode.title}: NOT READY: {reason}")
                failures += 1
                continue
            result = mode.run(question, settings)
            m = result.metrics
            status = "OK" if result.ok else f"FAILED: {result.error}"
            print(f"  {mode.title}")
            print(
                f"    {status} | {m.latency_s:.1f}s | cycles {m.model_cycles} "
                f"| searches {m.search_queries} | sources {len(result.citations)} "
                f"| ${m.total_cost_usd:.4f}"
            )
            for call in result.tool_calls:
                print(f"    tool: {call.name} {call.arguments}")
            print(f"    {' '.join((result.answer or '').split())[:220]}")
            if not result.ok:
                failures += 1
        print()

    if failures:
        print(f"{failures} problem(s) found")
        return 1
    print("live check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
