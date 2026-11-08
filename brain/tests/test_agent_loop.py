"""Tool-calling loop (LLM_MODE=grok shape) for the house and personal agents, with a scripted LLM."""
from __future__ import annotations

import pytest

from app import registry
from contracts.models import LLMResult, ToolCall


@pytest.fixture
def real_agents(use):
    if not registry.available("house", "real"):
        pytest.skip("house real not implemented yet")
    use(house="real", tools="real", personal="real", proposals="real", indicators="real",
        auditor="real", store="real", nessie="stub", llm="stub")


def _script(monkeypatch, steps: list[LLMResult]):
    """Tool-loop calls (tools passed) take the next scripted step; wording calls go to the stub."""
    llm, original, seen = registry.get("llm"), registry.get("llm").chat, []

    def chat(messages, tools=None):
        if tools:
            seen.append(messages)
            return steps.pop(0) if steps else LLMResult(text="")
        return original(messages, tools)

    monkeypatch.setattr(llm, "chat", chat)
    return seen


def test_read_tool_result_feeds_the_answer(real_agents, monkeypatch):
    seen = _script(monkeypatch, [LLMResult(text="", tool_calls=[ToolCall(name="house_status")]),
                                 LLMResult(text="Rent is due 2026-12-01 and Julian's share is $800.")])
    [reply] = registry.get("house").on_message("sam", "when is rent due and what's my share?")
    assert reply.text == "Rent is due 2026-12-01 and Julian's share is $800."
    assert "TOOL RESULTS" in seen[1][-1]["content"] and "Maple Court" in seen[1][-1]["content"]
    assert not registry.get("store").proposals()  # read-only


def test_invented_number_is_blocked_then_falls_back(real_agents, monkeypatch):
    _script(monkeypatch, [LLMResult(text="Sure, it's $999 each.")])
    [reply] = registry.get("house").on_message("sam", "how much is the couch each?")
    assert "999" not in reply.text


def test_private_balance_never_reaches_the_group(real_agents, monkeypatch):
    _script(monkeypatch, [LLMResult(text="Xander has $4,200.")])
    [reply] = registry.get("house").on_message("sam", "how much does alex have")
    assert "4,200" not in reply.text and "4200" not in reply.text


def test_what_if_does_not_propose(real_agents, monkeypatch):
    call = ToolCall(name="what_if_purchase", args={"item": "couch", "price": 1200, "months": 6})
    _script(monkeypatch, [LLMResult(text="", tool_calls=[call]),
                          LLMResult(text="Over 6 months it's $66.67/mo each.")])
    [reply] = registry.get("house").on_message("sam", "what about a 1200 couch over 6 months?")
    assert "$66.67" in reply.text and not registry.get("store").proposals()


def test_what_if_rejects_untyped_price(real_agents, monkeypatch):
    call = ToolCall(name="what_if_purchase", args={"item": "couch", "price": 5000})
    seen = _script(monkeypatch, [LLMResult(text="", tool_calls=[call]), LLMResult(text="How much is it?")])
    registry.get("house").on_message("sam", "what about a couch?")
    assert "nobody stated that price" in seen[1][-1]["content"]


def test_action_tool_ends_turn_with_months(real_agents, monkeypatch):
    call = ToolCall(name="group_affordability", args={"item": "couch", "price": 1200, "months": 6})
    _script(monkeypatch, [LLMResult(text="", tool_calls=[call])])
    replies = registry.get("house").on_message("alex", "lets get the 1200 couch over 6 months")
    assert "6 months" in replies[0].text
    [p] = registry.get("store").proposals()
    assert p.flow == "purchase"


def test_announcing_instead_of_calling_gets_nudged(real_agents, monkeypatch):
    seen = _script(monkeypatch, [LLMResult(text="I'll set up rent now."),
                                 LLMResult(text="", tool_calls=[ToolCall(name="start_bill", args={"bill": "rent"})])])
    registry.get("house").on_message("alex", "lets do rent")
    assert "call the tool now" in seen[1][-1]["content"]
    [p] = registry.get("store").proposals()
    assert p.flow == "rent"


def test_personal_dm_uses_own_tools(real_agents, monkeypatch):
    call = ToolCall(name="can_i_cover", args={"amount": 300, "by_date": "2026-12-05"})
    _script(monkeypatch, [LLMResult(text="", tool_calls=[call]),
                          LLMResult(text="Tight, Kevin, but you can cover $300 by 2026-12-05.")])
    [reply] = registry.get("personal").dm("jordan", "can i afford a 300 ticket next week?")
    assert reply.target.roommate_id == "jordan" and "$300" in reply.text


def test_personal_dm_blocks_other_roommates_balance(real_agents, monkeypatch):
    _script(monkeypatch, [LLMResult(text="Xander has $4,200, ask them.")])
    [reply] = registry.get("personal").dm("jordan", "how much does alex have")
    assert "4,200" not in reply.text
