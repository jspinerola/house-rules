"""House agent routes group messages to a flow via LLM tool calls, with a keyword fallback."""
from __future__ import annotations

import pytest

from app import registry
from contracts.models import LLMResult, ToolCall


@pytest.fixture
def real_house(use):
    if not registry.available("house", "real"):
        pytest.skip("house real not implemented yet")
    use(house="real", tools="real", personal="real", proposals="real",
        auditor="real", store="real", nessie="stub", llm="stub")


def _scripted_router(monkeypatch, calls: list[ToolCall]):
    llm = registry.get("llm")
    original = llm.chat

    def chat(messages, tools=None):
        if tools:  # the router call; wording calls go to the stub as usual
            return LLMResult(text="", tool_calls=calls)
        return original(messages, tools)

    monkeypatch.setattr(llm, "chat", chat)


def test_llm_tool_call_starts_rent_without_keywords(real_house, monkeypatch):
    _scripted_router(monkeypatch, [ToolCall(name="start_bill", args={"bill": "rent"})])
    replies = registry.get("house").on_message("alex", "hey the landlord wants his money soon")
    [p] = registry.get("store").proposals()
    assert p.flow == "rent" and p.status == "pending"
    assert any(r.target.type == "group" for r in replies)
    assert any(r.target.type == "dm" and r.target.roommate_id == "jordan" for r in replies)


def test_keyword_fallback_starts_rent_in_stub_mode(real_house):
    registry.get("house").on_message("alex", "rent's due soon")
    [p] = registry.get("store").proposals()
    assert p.flow == "rent"


def test_rent_is_not_proposed_twice(real_house):
    house = registry.get("house")
    house.on_message("alex", "rent's due soon")
    replies = house.on_message("sam", "rent is due")
    assert len(registry.get("store").proposals()) == 1
    assert "already" in replies[0].text


def test_llm_tool_call_routes_affordability(real_house, monkeypatch):
    _scripted_router(monkeypatch, [ToolCall(name="group_affordability", args={})])
    replies = registry.get("house").on_message("alex", "is a $1,200 couch doable for us?")
    assert "3 months" in replies[0].text


def test_small_talk_gets_the_intro(real_house):
    replies = registry.get("house").on_message("alex", "hello")
    assert not registry.get("store").proposals()
    assert replies and replies[0].target.type == "group"
