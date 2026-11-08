"""Purchase rules and one-off uneven splits (docs/RULES_AND_PROFILES.md), scripted LLM."""
from __future__ import annotations

from app import registry
from contracts.models import HouseRule
from tests.test_agent_loop import _script, real_agents  # noqa: F401  (fixture)
from tests.test_rules import _call, _vote

HALF = {"Xander": 50, "Julian": 25, "Kevin": 25}


def _save_half_rule():
    registry.get("store").save_house_rule(HouseRule(
        id="rule-purchase", bill_type="purchase", split={"alex": 0.5}, source_text="Xander keeps the furniture"))


def _paid_by(p, rid):
    return round(sum(leg.amount for leg in p.legs if leg.from_ == rid and leg.type == "scheduled_transfer"), 2)


def test_even_couch_is_unchanged_without_a_rule(real_agents):
    aff = registry.get("tools").group_affordability("couch", 1200)
    assert aff.plan.months == 3 and aff.plan.per_person_monthly == 133.33 and aff.plan.monthly == {}


def test_purchase_rule_vote_previews_on_an_example(real_agents, monkeypatch):
    _script(monkeypatch, [_call("propose_rule", bill="purchase", shares={"Xander": 50},
                                reason="Xander keeps the furniture when we move out")])
    [reply] = registry.get("house").on_message("sam", "xander keeps the furniture so xander pays half of shared stuff")
    assert "$50" in reply.text and "$25" in reply.text
    _vote("alex", "sam", "jordan")
    assert registry.get("store").house_rule("purchase").split == {"alex": 0.5}


def test_purchase_rule_drives_the_couch_plan(real_agents, monkeypatch):
    _save_half_rule()
    aff = registry.get("tools").group_affordability("couch", 1200)
    assert aff.plan.months == 3 and aff.plan.monthly == {"alex": 200, "sam": 100, "jordan": 100}
    _script(monkeypatch, [_call("group_affordability", item="couch", price=1200)])
    [reply] = registry.get("house").on_message("jordan", "can we afford a 1200 couch")
    assert "Xander $200/mo" in reply.text and "Julian $100/mo" in reply.text
    [p] = registry.get("store").proposals()
    assert next(leg for leg in p.legs if leg.type == "purchase").from_ == "alex"
    assert (_paid_by(p, "sam"), _paid_by(p, "jordan")) == (300, 300)


def test_one_off_split_applies_once_and_saves_nothing(real_agents, monkeypatch):
    _script(monkeypatch, [_call("group_affordability", item="couch", price=1200, shares=HALF,
                                reason="it goes in Xander's room")])
    [reply] = registry.get("house").on_message("sam", "xander pays half of the 1200 couch since its in his room")
    assert "it goes in Xander's room" in reply.text or "$200" in reply.text
    assert registry.get("store").house_rule("purchase") is None
    [p] = registry.get("store").proposals()
    assert (_paid_by(p, "sam"), _paid_by(p, "jordan")) == (300, 300)


def test_uneven_cents_still_add_up(real_agents, monkeypatch):
    _script(monkeypatch, [_call("group_affordability", item="desk", price=1000, months=3, shares={"Xander": 50})])
    registry.get("house").on_message("sam", "1000 desk, xander pays half, over 3 months")
    [p] = registry.get("store").proposals()
    buyer = next(leg for leg in p.legs if leg.type == "purchase").from_
    owed = registry.get("tools").split_bill("purchase", 1000, rule=HouseRule(
        id="x", bill_type="purchase", split={"alex": 0.5}, source_text="x")).shares
    for rid in ("alex", "sam", "jordan"):
        if rid != buyer:
            assert _paid_by(p, rid) == owed[rid]
    assert round(sum(owed.values()), 2) == 1000


def test_what_if_with_shares_proposes_nothing(real_agents, monkeypatch):
    from tests.test_agent_loop import LLMResult, ToolCall
    call = ToolCall(name="what_if_purchase", args={"item": "couch", "price": 1200, "months": 3, "shares": HALF})
    seen = _script(monkeypatch, [LLMResult(text="", tool_calls=[call]),
                                 LLMResult(text="Xander would be $200/mo, Julian and Kevin $100/mo.")])
    [reply] = registry.get("house").on_message("sam", "what if xander paid half of a 1200 couch?")
    assert "$200/mo" in reply.text and not registry.get("store").proposals()
    assert any('"name": "Xander", "pays_total": 600.0, "pays_per_month": 200.0' in m["content"] for m in seen[-1])


def test_rent_rules_still_reject_purchase_as_a_bill(real_agents, monkeypatch):
    seen = _script(monkeypatch, [_call("start_bill", bill="purchase"), _call("house_status")])
    registry.get("house").on_message("alex", "start the purchase bill")
    assert any("unknown bill" in m["content"] for m in seen[-1])
