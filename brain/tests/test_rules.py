"""Chat-set house rules (docs/RULES_AND_PROFILES.md, REQUIREMENTS A7) with a scripted LLM."""
from __future__ import annotations

import pytest

from app import registry
from contracts.models import LLMResult, ToolCall
from tests.test_agent_loop import _script, real_agents  # noqa: F401  (fixture)

MASTER = {"bill": "rent", "shares": {"Alex": 40, "Sam": 30, "Jordan": 30}, "reason": "Alex has the master bedroom"}


def _call(name, **args):
    return LLMResult(text="", tool_calls=[ToolCall(name=name, args=args)])


def _vote(*voters, text="yes"):
    proposals = registry.get("proposals")
    return [proposals.record_reply(r, text) for r in voters][-1]


def _rent_shares():
    return registry.get("tools").split_bill("rent", 2400).shares


def test_rule_previews_then_saves_after_everyone_agrees(real_agents, monkeypatch):
    _script(monkeypatch, [_call("propose_rule", **MASTER)])
    [reply] = registry.get("house").on_message("alex", "alex has the master so rent should be 40/30/30")
    assert "$960" in reply.text and "$720" in reply.text
    [p] = registry.get("store").proposals()
    assert p.flow == "rule" and p.legs == [] and p.status == "pending"
    assert _rent_shares() == {"alex": 800, "sam": 800, "jordan": 800}  # nothing changes before the vote

    p = _vote("alex", "sam", "jordan")
    assert p.status == "executed"
    assert _rent_shares() == {"alex": 960, "sam": 720, "jordan": 720}
    rule = registry.get("store").house_rule("rent")
    assert rule.source_text == "Alex has the master bedroom" and set(rule.confirmed_by) == {"alex", "sam", "jordan"}


def test_next_rent_uses_the_rule(real_agents, monkeypatch):
    _script(monkeypatch, [_call("propose_rule", **MASTER), _call("start_bill", bill="rent")])
    house = registry.get("house")
    house.on_message("alex", "rent 40/30/30 since alex has the master")
    _vote("alex", "sam", "jordan")
    house.on_message("alex", "lets do rent")
    rent = next(p for p in registry.get("store").proposals() if p.flow == "rent")
    sam_leg = next(leg for leg in rent.legs if leg.from_ == "sam")
    assert sam_leg.amount == 720


def test_pending_rent_keeps_its_split(real_agents, monkeypatch):
    _script(monkeypatch, [_call("start_bill", bill="rent"), _call("propose_rule", **MASTER)])
    house = registry.get("house")
    house.on_message("alex", "lets do rent")
    [reply] = house.on_message("alex", "actually alex has the master, 40/30/30")
    assert "keeps its current split" in reply.text
    rent = next(p for p in registry.get("store").proposals() if p.flow == "rent")
    assert next(leg for leg in rent.legs if leg.from_ == "sam").amount == 800


@pytest.mark.parametrize("shares, error", [
    ({"Alex": 60, "Sam": 50}, "more than 100%"),
    ({"Alex": 40, "Sam": 30, "Jordan": 20}, "must add up to 100%"),
    ({"Bob": 40}, "unknown roommate"),
    ({"Alex": -5}, "percent from 0 to 100"),
])
def test_invalid_rules_are_rejected_with_a_reason(real_agents, monkeypatch, shares, error):
    seen = _script(monkeypatch, [_call("propose_rule", bill="rent", shares=shares), LLMResult(text="Hmm, check that.")])
    registry.get("house").on_message("alex", "new rent split")
    assert error in seen[1][-1]["content"]
    assert not registry.get("store").proposals()


def test_one_no_rejects_the_rule(real_agents, monkeypatch):
    _script(monkeypatch, [_call("propose_rule", **MASTER)])
    registry.get("house").on_message("alex", "40/30/30 rent")
    p = _vote("alex", text="no")
    assert p.status == "rejected" and registry.get("store").house_rule("rent") is None


def test_removing_a_rule_needs_everyone(real_agents, monkeypatch):
    _script(monkeypatch, [_call("remove_rule", bill="electric")])
    [reply] = registry.get("house").on_message("sam", "can we go back to an even electric split")
    assert "$50" in reply.text
    _vote("alex", "sam")
    assert registry.get("store").house_rule("electric") is not None  # Jordan hasn't agreed yet
    _vote("jordan")
    assert registry.get("store").house_rule("electric") is None
    assert registry.get("tools").split_bill("electric", 150).shares == {"alex": 50, "sam": 50, "jordan": 50}


def test_rule_votes_never_touch_the_treasurer(real_agents, monkeypatch):
    def boom(pid):
        raise AssertionError("treasurer called for a rule")
    monkeypatch.setattr(registry.get("treasurer"), "execute", boom)
    _script(monkeypatch, [_call("propose_rule", **MASTER)])
    registry.get("house").on_message("alex", "40/30/30 rent")
    assert _vote("alex", "sam", "jordan").status == "executed"


def test_state_shows_rules(real_agents):
    from app import views
    assert [r.bill_type for r in views.house_state().rules] == ["electric"]
