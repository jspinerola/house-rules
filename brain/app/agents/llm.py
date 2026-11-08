"""LLM_MODE=grok adapter: wraps wellness.llm.GrokLLM into the LLM Protocol.

A timeout or network error falls back to the stub's scripted reply (REQUIREMENTS M6), and
the fallback is traced so it is never silent.
"""
from __future__ import annotations

import json
import os
import socket
import urllib.error

from contracts.models import LLMResult, ToolCall
from wellness.llm import GrokLLM as WorkshopGrok

from .. import trace
from ..stubs.llm import StubLLM

try:
    import openai
    _GROK_TRANSPORT = (openai.APITimeoutError, openai.APIConnectionError)
except ImportError:  # pragma: no cover
    _GROK_TRANSPORT = ()


class GrokLLM:
    def __init__(self) -> None:
        if not os.environ.get("XAI_API_KEY"):
            raise ValueError("LLM_MODE=grok needs XAI_API_KEY")
        self._grok = WorkshopGrok(timeout=8)
        self._fallback = StubLLM()

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResult:
        try:
            msg = self._grok.chat(messages, tools)
        except (TimeoutError, socket.timeout, urllib.error.URLError, *_GROK_TRANSPORT) as e:
            trace.log("house", "llm_fallback", f"grok unavailable ({e}); using scripted reply")
            return self._fallback.chat(messages, tools)
        calls = [ToolCall(name=c["function"]["name"], args=json.loads(c["function"].get("arguments") or "{}"))
                 for c in msg.get("tool_calls") or []]
        return LLMResult(text=msg.get("content") or "", tool_calls=calls)
