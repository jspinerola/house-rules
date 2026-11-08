"""Scripted LLM: returns the code-built DRAFT when given one, else the script for the flow."""
from __future__ import annotations

from contracts.models import LLMResult

from .. import fixtures

FLOW_SCRIPTS = {"rent": "rent_group", "front": "rent_dm_jordan", "couch": "couch_group"}


class StubLLM:
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
        last = messages[-1]["content"] if messages else ""
        if "DRAFT:" in last:
            return LLMResult(text=last.split("DRAFT:", 1)[1].strip())
        system = messages[0]["content"] if messages else ""
        scripts = fixtures.expected().scripts
        for flow, key in FLOW_SCRIPTS.items():
            if f"FLOW:{flow}" in system:
                return LLMResult(text=getattr(scripts, key))
        return LLMResult(text=scripts.hello_group)
