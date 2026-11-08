"""Personal profiles from bank data + DM-set preferences (docs/RULES_AND_PROFILES.md, A9)."""
from __future__ import annotations

from app import registry
from contracts.models import LLMResult, Preferences, ToolCall
from tests.test_agent_loop import _script, real_agents  # noqa: F401  (fixture)


def _prefs(rid, **kw):
    registry.get("store").save_preferences(rid, Preferences(**kw))


def test_jordan_has_gig_income_and_subscriptions(real_agents):
    p = registry.get("indicators").profile("jordan")
    assert p.income_pattern == "steady_plus_side"
    assert p.regular_pay == 1350 and abs(p.side_income_monthly - 374.89) < 0.01
    assert [(r.name, r.amount, r.next_date) for r in p.recurring] == [
        ("StreamFlix", 15.49, "2026-12-05"), ("Phone Plan", 45.0, "2026-12-08")]
    assert registry.get("indicators").profile("alex").income_pattern == "steady"


def test_housing_cost_counts_rent(real_agents):
    ind = registry.get("indicators").compute("jordan")
    assert ind["housing_cost_ratio"].value > 0.4 and ind["housing_cost_ratio"].status == "risk"


def test_executed_money_moves_the_indicators(real_agents):
    indicators = registry.get("indicators")
    before = indicators.compute("alex")["runway_days"].value
    registry.get("house").on_event("rent_due")
    for rid in ("alex", "sam", "jordan"):
        registry.get("proposals").record_reply(rid, "yes")
    after = indicators.compute("alex")["runway_days"].value
    assert after != before  # Alex paid Maple Court $2,400 through Nessie


def test_cushion_turns_ok_into_tight(real_agents):
    tools, today = registry.get("tools"), registry.get("store").today()
    assert tools.can_cover("sam", 133.33, today).level == "ok"
    _prefs("sam", min_buffer=2500)
    ans = tools.can_cover("sam", 133.33, today)
    assert (ans.level, ans.reason) == ("tight", "cushion")


def test_savings_goal_reserves_money(real_agents):
    tools, today = registry.get("tools"), registry.get("store").today()
    _prefs("sam", savings_monthly=2400, savings_label="Japan")
    assert tools.can_cover("sam", 133.33, today).reason == "savings_goal"


def test_front_cap_changes_who_fronts(real_agents):
    tools = registry.get("tools")
    assert tools.payday_plan("jordan", 800).fronter == "alex"
    _prefs("alex", front_cap=500)
    assert tools.payday_plan("jordan", 800).fronter == "sam"


def test_nobody_willing_to_front_holds_the_bill(real_agents):
    _prefs("alex", front_cap=100)
    _prefs("sam", front_cap=100)
    [reply] = registry.get("house").on_event("rent_due")
    assert "nobody is set up to front" in reply.text
    assert not registry.get("store").proposals()


def test_release_never_carries_the_reason(real_agents):
    _prefs("sam", min_buffer=2500)
    from contracts.models import Ask
    rel = registry.get("personal").ask("sam", Ask(amount=133.33, by_date="2026-11-28", purpose="couch"))
    assert set(rel.model_dump()) == {"level", "earliest_date"} and rel.level == "tight"


def test_private_profile_figures_stay_out_of_the_group(real_agents):
    auditor = registry.get("auditor")
    _prefs("sam", min_buffer=2500)
    assert not auditor.check("Jordan makes $374.89 on the side.", set(), "group").ok
    assert not auditor.check("Sam wants to keep $2,500.", set(), "group").ok
    assert auditor.check("You make about $374.89 a month from gigs.", {374.89}, "jordan").ok
    assert auditor.check("Alex pays $45 for electric.", {45.0}, "group").ok  # same number, from a tool


def test_dm_preference_is_saved_and_used(real_agents, monkeypatch):
    call = ToolCall(name="set_preference", args={"kind": "min_buffer", "value": 2500})
    _script(monkeypatch, [LLMResult(text="", tool_calls=[call]),
                          LLMResult(text="Done, Sam. I'll keep at least $2,500 in your checking.")])
    [reply] = registry.get("personal").dm("sam", "im saving for japan, keep $2,500 in checking")
    assert "$2,500" in reply.text
    assert registry.get("store").get_preferences("sam").min_buffer == 2500
    trace = registry.get("store").recent_trace(10)
    assert any(e.event == "preference_set" and "2500" not in e.detail for e in trace)


def test_bank_view_carries_the_profile(real_agents):
    from app import views
    view = views.bank_view("jordan")
    assert view.profile is not None and view.profile.income_pattern == "steady_plus_side"
