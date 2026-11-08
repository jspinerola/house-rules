"""REQUIREMENTS M6 done-when: call a tool through Grok and get a tool_call back.

Requires XAI_API_KEY and GROK_MODEL (defaults to grok-4.7). Not run in CI.
Usage (from repo root, with brain deps installed):

  set LLM_MODE=grok
  python scripts/grok_llm_tool_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "brain")]

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

os.environ.setdefault("LLM_MODE", "grok")
os.environ.setdefault("GROK_MODEL", "grok-4.7")

from app import registry  # noqa: E402


TOOLS = [{
    "type": "function",
    "function": {
        "name": "can_cover",
        "description": "Whether a roommate can cover an amount by a date.",
        "parameters": {
            "type": "object",
            "properties": {
                "roommate_id": {"type": "string"},
                "amount": {"type": "number"},
                "date": {"type": "string"},
            },
            "required": ["roommate_id", "amount", "date"],
        },
    },
}]


def main() -> int:
    if not os.environ.get("XAI_API_KEY", "").strip():
        print("XAI_API_KEY is required", file=sys.stderr)
        return 1
    registry.reset()
    out = registry.get("llm").chat(
        [{"role": "user",
          "content": "Call can_cover for jordan, amount 800, date 2026-11-30. Do not answer in text."}],
        tools=TOOLS,
    )
    print(f"text={out.text!r}")
    print(f"tool_calls={[(c.name, c.args) for c in out.tool_calls]}")
    if not out.tool_calls:
        print("expected at least one tool_call", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
