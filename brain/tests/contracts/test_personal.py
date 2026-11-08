"""M7 Personal agent: ask releases ok/tight/no only; DMs use own numbers via voice+auditor.

Stub stays fixture-canned for dm/explain; multi-path DM and explain hardening is real-only.
"""
from __future__ import annotations

import pytest
from contracts.models import Ask, Leg, LLMResult, Release

from app import fixtures, registry
from app.agents import voice
from tests.conftest import impl_params


def _use_real(use):
    if not registry.available("personal", "real"):
        pytest.skip("personal real not implemented yet")
    # Nessie stays stub (live not built); matches conftest ALL_REAL profile.
    use(personal="real", tools="real", indicators="real", store="real", nessie="stub")


def _trace_pairs():
    return [(e.agent, e.event) for e in registry.get("store").recent_trace()]


@impl_params("personal")
def test_jordan_release_is_level_and_date_only(use, mode):
    use(personal=mode)
    rel = registry.get("personal").ask("jordan", Ask(amount=800, by_date="2026-11-30", purpose="rent"))
    assert isinstance(rel, Release)
    assert rel.model_dump() == {"level": "no", "earliest_date": "2026-12-15"}


@impl_params("personal")
def test_dm_goes_to_that_roommate(use, mode):
    use(personal=mode)
    replies = registry.get("personal").dm("sam", "what's my runway?")
    assert replies and all(r.target.type == "dm" and r.target.roommate_id == "sam" for r in replies)


@impl_params("personal")
def test_jordan_dm_explains_fronting(use, mode):
    use(personal=mode)
    registry.get("house").on_event("rent_due")
    p = registry.get("store").proposals()[0]
    replies = registry.get("personal").explain("jordan", p)
    assert replies and "Xander" in replies[0].text and "2026-12-16" in replies[0].text


@impl_params("personal")
def test_alex_dm_explains_fronting(use, mode):
    use(personal=mode)
    registry.get("house").on_event("rent_due")
    p = registry.get("store").proposals()[0]
    replies = registry.get("personal").explain("alex", p)
    assert replies and "Kevin" in replies[0].text and "2026-12-16" in replies[0].text


def test_alex_sam_ask_ok_no_date(use):
    _use_real(use)
    ask = Ask(amount=800, by_date="2026-11-30", purpose="rent")
    personal = registry.get("personal")
    for rid in ("alex", "sam"):
        rel = personal.ask(rid, ask)
        assert rel.level == "ok" and rel.earliest_date is None


def test_jordan_ask_traces_answered(use):
    _use_real(use)
    registry.get("personal").ask("jordan", Ask(amount=800, by_date="2026-11-30", purpose="rent"))
    pairs = _trace_pairs()
    assert ("personal:jordan", "answered") in pairs
    assert any(e.agent == "personal:jordan" and e.event == "answered" and "no" in e.detail
               for e in registry.get("store").recent_trace())


def test_jordan_dm_balance_own_number(use):
    _use_real(use)
    use(auditor="real", llm="stub")
    replies = registry.get("personal").dm("jordan", "what's my balance?")
    text = replies[0].text
    assert "310" in text


def test_sam_dm_runway_from_indicators(use):
    _use_real(use)
    runway = registry.get("indicators").compute("sam")["runway_days"].value
    replies = registry.get("personal").dm("sam", "what's my runway?")
    assert f"{runway:g}" in replies[0].text


def test_dm_blocks_leak_via_speak(use, monkeypatch):
    _use_real(use)
    use(auditor="real", llm="stub")

    class LeakyLLM:
        def chat(self, messages, tools=None):
            return LLMResult(text="Xander has $4,200 in checking.")

    monkeypatch.setitem(registry._cache, ("llm", registry.mode("llm")), LeakyLLM())
    replies = registry.get("personal").dm("jordan", "what's my balance?")
    text = replies[0].text
    assert "4200" not in text.replace(",", "")
    assert "4,200" not in text
    assert "310" in text or text == voice.SAFE


def test_dm_pending_proposal_nudge(use):
    _use_real(use)
    props = registry.get("proposals")
    props.create("utility", "Electric bill", [
        Leg(type="transfer", **{"from": "sam"}, to="alex", amount=60, date="2026-11-28"),
    ], ["alex", "sam"])
    replies = registry.get("personal").dm("sam", "hi")
    assert "Electric bill" in replies[0].text
    assert "yes" in replies[0].text.lower()


def test_explain_couch_sums_jordan_legs(use):
    _use_real(use)
    sp = fixtures.expected().proposals["couch"]
    legs = [leg.model_copy() for leg in sp.legs]
    p = registry.get("proposals").create(sp.flow, sp.title, legs, list(sp.required_approvers))
    replies = registry.get("personal").explain("jordan", p)
    assert replies
    text = replies[0].text
    assert "133.33" in text or "400" in text
