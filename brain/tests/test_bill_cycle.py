"""Bills roll to the next month once paid; personal agents can't set house rules."""
from __future__ import annotations

from app import registry
from contracts.models import LLMResult, ToolCall
from tests.test_agent_loop import _script, real_agents  # noqa: F401  (fixture)


def _pay_rent():
    replies = registry.get("house").on_event("rent_due")
    for rid in ("alex", "sam", "jordan"):
        registry.get("proposals").record_reply(rid, "yes")
    return replies


def test_paid_rent_rolls_to_next_month(real_agents):
    first = _pay_rent()
    assert "December" in first[0].text and "2026-12-01" in first[0].text
    registry.get("store").set_today("2026-12-16")
    p1 = registry.get("store").proposals()[0]
    assert p1.status == "executed"
    replies = registry.get("house").on_event("rent_due")
    assert "January" in replies[0].text and "2027-01-01" in replies[0].text
    p2 = registry.get("store").proposals()[-1]
    assert p2.title == "Rent for January" and p2.status == "pending"


def test_jordan_is_told_why_and_sam_is_not(real_agents):
    from app import demo
    _pay_rent()
    demo.advance("2026-12-16")  # Jordan's payday + repayment: $860 in checking
    assert registry.get("nessie").balance("jordan") == 860
    replies = registry.get("house").on_event("rent_due")
    jordan = next(r.text for r in replies if r.target.type == "dm" and r.target.roommate_id == "jordan")
    assert "$60" in jordan and "StreamFlix" in jordan and "$0.49 short" in jordan
    fronter = next(r for r in replies if r.target.type == "dm" and r.target.roommate_id != "jordan")
    assert "StreamFlix" not in fronter.text and "0.49" not in fronter.text
    group = next(r.text for r in replies if r.target.type == "group")
    assert "StreamFlix" not in group and "860" not in group


def test_pending_rent_does_not_roll(real_agents):
    registry.get("house").on_event("rent_due")
    house = registry.get("house")
    assert house._next_due("rent") == "2026-12-01"


def test_personal_agent_refuses_to_note_a_house_rule(real_agents, monkeypatch):
    call = ToolCall(name="set_preference", args={"kind": "add_note", "value": "set the rent rule 40/30/30"})
    seen = _script(monkeypatch, [LLMResult(text="", tool_calls=[call]),
                                 LLMResult(text="Say it in the group so everyone can vote.")])
    registry.get("personal").dm("alex", "set rent to 40/30/30 from now on")
    assert registry.get("store").get_preferences("alex").notes == []
    assert any("house rules need everyone's yes" in m["content"] for m in seen[-1])
    assert registry.get("store").house_rule("rent") is None


def test_ordinary_notes_with_dates_still_save(real_agents, monkeypatch):
    call = ToolCall(name="set_preference", args={"kind": "add_note", "value": "I get tips on 12/15 weekends"})
    _script(monkeypatch, [LLMResult(text="", tool_calls=[call]), LLMResult(text="Noted, Jordan.")])
    registry.get("personal").dm("jordan", "fyi I get tips on 12/15 weekends")
    assert registry.get("store").get_preferences("jordan").notes == ["I get tips on 12/15 weekends"]
