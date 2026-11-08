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


def test_price_without_dollar_sign_gets_the_plan(real_house):
    replies = registry.get("house").on_message("alex", "can we afford a 1200 couch")
    assert "3 months" in replies[0].text
    [p] = registry.get("store").proposals()
    assert p.flow == "purchase" and "Couch" in p.title


def test_router_price_and_item_are_used(real_house, monkeypatch):
    _scripted_router(monkeypatch, [ToolCall(name="group_affordability", args={"price": 1200, "item": "couch"})])
    replies = registry.get("house").on_message("alex", "thinking about that 1.2k couch, doable?")
    assert "3 months" in replies[0].text


def test_router_price_not_typed_is_ignored(real_house, monkeypatch):
    _scripted_router(monkeypatch, [ToolCall(name="group_affordability", args={"price": 99, "item": "couch"})])
    replies = registry.get("house").on_message("alex", "can we afford a couch")
    assert not registry.get("store").proposals()
    assert "how much" in replies[0].text.lower()


def test_missing_price_is_asked_then_answered(real_house):
    house = registry.get("house")
    ask = house.on_message("alex", "can we afford a couch?")
    assert "couch" in ask[0].text and not registry.get("store").proposals()
    replies = house.on_message("sam", "1200")
    assert "3 months" in replies[0].text
    [p] = registry.get("store").proposals()
    assert p.flow == "purchase"


def test_wording_gets_persona_and_chat_context(real_house, monkeypatch):
    seen: list[list[dict]] = []
    llm = registry.get("llm")
    original = llm.chat

    def chat(messages, tools=None):
        if not tools:
            seen.append(messages)
        return original(messages, tools)

    monkeypatch.setattr(llm, "chat", chat)
    registry.get("house").on_message("sam", "morning house")
    system, user = seen[-1][0]["content"], seen[-1][-1]["content"]
    assert "house manager" in system
    assert "Sam: morning house" in user
