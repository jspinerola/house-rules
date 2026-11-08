"""M6 LLM adapter: StubLLM scripts + Grok (OpenAI SDK) with tool calling and timeout fallback.

Live network is skipped unless RUN_LIVE_GROK=1. Unit tests mock wellness.llm.GrokLLM.
"""
from __future__ import annotations

import os
import urllib.error

import pytest

from contracts.models import LLMResult

from app import fixtures, registry


def _trace_pairs():
    return [(e.agent, e.event) for e in registry.get("store").recent_trace()]


def _use_grok(use, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("GROK_MODEL", "grok-4.7")
    use(llm="grok")


@pytest.mark.parametrize("mode", ["stub", pytest.param("grok", marks=pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_GROK"), reason="live Grok runs only with RUN_LIVE_GROK=1"))])
def test_llm_contract(use, mode):
    use(llm=mode)
    out = registry.get("llm").chat([{"role": "system", "content": "FLOW:couch"},
                                    {"role": "user", "content": "DRAFT: hello there"}])
    assert isinstance(out, LLMResult) and out.text


def test_stub_draft_passthrough(use):
    use(llm="stub")
    out = registry.get("llm").chat([{"role": "user", "content": "DRAFT: foo"}])
    assert out.text == "foo" and out.tool_calls == []


def test_stub_flow_scripts(use):
    use(llm="stub")
    scripts = fixtures.expected().scripts
    llm = registry.get("llm")
    assert llm.chat([{"role": "system", "content": "FLOW:rent"},
                     {"role": "user", "content": "hi"}]).text == scripts.rent_group
    assert llm.chat([{"role": "system", "content": "FLOW:front"},
                     {"role": "user", "content": "hi"}]).text == scripts.rent_dm_jordan
    assert llm.chat([{"role": "system", "content": "FLOW:couch"},
                     {"role": "user", "content": "hi"}]).text == scripts.couch_group


def test_stub_hello_without_flow(use):
    use(llm="stub")
    out = registry.get("llm").chat([{"role": "system", "content": "RULES"},
                                    {"role": "user", "content": "hi"}])
    assert out.text == fixtures.expected().scripts.hello_group


def test_stub_tool_calls_empty(use):
    use(llm="stub")
    out = registry.get("llm").chat([{"role": "user", "content": "DRAFT: x"}],
                                   tools=[{"type": "function", "function": {"name": "can_cover"}}])
    assert out.tool_calls == []


def test_grok_requires_xai_api_key(use, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("GROK_MODEL", "grok-4.7")
    use(llm="grok")
    with pytest.raises(ValueError, match="XAI_API_KEY"):
        registry.get("llm")


def test_grok_maps_tool_calls(use, monkeypatch):
    _use_grok(use, monkeypatch)

    def fake_chat(self, messages, tools=None):
        return {
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "type": "function",
                "function": {"name": "can_cover", "arguments": '{"roommate_id":"jordan","amount":800}'},
            }],
        }

    monkeypatch.setattr("wellness.llm.GrokLLM.chat", fake_chat)
    out = registry.get("llm").chat([{"role": "user", "content": "check cover"}],
                                   tools=[{"type": "function", "function": {"name": "can_cover"}}])
    assert out.text == ""
    assert len(out.tool_calls) == 1
    assert out.tool_calls[0].name == "can_cover"
    assert out.tool_calls[0].args == {"roommate_id": "jordan", "amount": 800}


def test_grok_fallback_on_transport_error(use, monkeypatch):
    _use_grok(use, monkeypatch)

    def boom(self, messages, tools=None):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr("wellness.llm.GrokLLM.chat", boom)
    out = registry.get("llm").chat([{"role": "system", "content": "FLOW:couch"},
                                    {"role": "user", "content": "hi"}])
    assert out.text == fixtures.expected().scripts.couch_group
    assert ("house", "llm_fallback") in _trace_pairs()


def test_grok_fallback_on_timeout(use, monkeypatch):
    _use_grok(use, monkeypatch)

    def boom(self, messages, tools=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr("wellness.llm.GrokLLM.chat", boom)
    out = registry.get("llm").chat([{"role": "system", "content": "FLOW:rent"},
                                    {"role": "user", "content": "hi"}])
    assert out.text == fixtures.expected().scripts.rent_group
    assert ("house", "llm_fallback") in _trace_pairs()


def test_workshop_grok_uses_openai_sdk(monkeypatch):
    """REQUIREMENTS M6: Grok goes through the OpenAI SDK at api.x.ai/v1 with an 8s timeout."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("GROK_MODEL", "grok-4.7")

    created: dict = {}

    class FakeCompletions:
        def create(self, **kwargs):
            created["create"] = kwargs
            msg = type("Msg", (), {
                "content": "ok",
                "tool_calls": None,
                "model_dump": lambda self=None: {"content": "ok", "tool_calls": None},
            })()
            return type("Resp", (), {"choices": [type("C", (), {"message": msg})()]})()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **kwargs):
            created["client"] = kwargs
            self.chat = FakeChat()

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)

    from wellness.llm import GrokLLM
    out = GrokLLM(timeout=8).chat(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "can_cover"}}],
    )
    assert created["client"]["base_url"] == "https://api.x.ai/v1"
    assert created["client"].get("api_key") == "test-key"
    assert created["client"].get("timeout") == 8
    assert created["create"]["model"] == "grok-4.7"
    assert created["create"]["tools"]
    assert created["create"].get("timeout") in (8, None) or "timeout" not in created["create"]
    assert out["content"] == "ok"


@pytest.mark.skipif(not os.environ.get("RUN_LIVE_GROK"), reason="live Grok runs only with RUN_LIVE_GROK=1")
def test_live_grok_returns_tool_call(use):
    use(llm="grok")
    tools = [{
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
    out = registry.get("llm").chat(
        [{"role": "user", "content": "Call can_cover for jordan, amount 800, date 2026-11-30. Do not answer in text."}],
        tools=tools,
    )
    assert out.tool_calls, out
