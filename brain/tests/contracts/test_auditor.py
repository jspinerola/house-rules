"""M5 Auditor: number allowlist + balance/income privacy (AUDITOR_MODE=real).

Stub stays always-ok; leak/invented/DM/date/voice-fallback rules are real-only.
"""
from __future__ import annotations

import pytest
from contracts.models import LLMResult

from app import fixtures, registry
from app.agents import voice
from tests.conftest import impl_params

RENT = fixtures.expected().scripts.rent_group


def _use_real(use):
    if not registry.available("auditor", "real"):
        pytest.skip("auditor real not implemented yet")
    use(auditor="real")


def _trace_pairs():
    return [(e.agent, e.event) for e in registry.get("store").recent_trace()]


@impl_params("auditor")
def test_correct_rent_message_passes(use, mode):
    use(auditor=mode)
    assert registry.get("auditor").check(RENT, {2400, 800}, "group").ok


def test_jordan_310_blocked_in_group(use):
    """Done-when: group draft with Jordan's $310 is blocked and traced."""
    _use_real(use)
    a = registry.get("auditor")
    res = a.check("Jordan only has $310, so Alex fronts $800.", {800, 310}, "group")
    assert not res.ok
    assert any("310" in r for r in res.reasons)
    assert ("auditor", "blocked") in _trace_pairs()


def test_invented_number_blocked(use):
    _use_real(use)
    res = registry.get("auditor").check("That's $999 each.", {800}, "group")
    assert not res.ok


def test_income_blocked_in_group(use):
    """Income stays private in group even if it appears on the allowlist."""
    _use_real(use)
    res = registry.get("auditor").check(
        "Alex makes $5800 a month.", {5800}, "group")
    assert not res.ok
    assert any("5800" in r or "income" in r.lower() or "pay" in r.lower() for r in res.reasons)


def test_own_dm_allows_own_balance(use):
    _use_real(use)
    assert registry.get("auditor").check(
        "Your balance is $310.", {310}, "jordan").ok


def test_dm_blocks_other_roommate_balance(use):
    _use_real(use)
    res = registry.get("auditor").check(
        "Alex has $4200 in checking.", {4200}, "jordan")
    assert not res.ok


def test_dates_are_not_amounts(use):
    _use_real(use)
    text = "Repay $800 on 2026-12-16 (the 16th)."
    assert registry.get("auditor").check(text, {800}, "group").ok


def test_speak_falls_back_after_two_blocks(use, monkeypatch):
    """Blocked twice → SAFE template; auditor fallback is traced."""
    _use_real(use)

    class LeakyLLM:
        def chat(self, messages, tools=None):
            return LLMResult(text="Jordan only has $310 left.")

    monkeypatch.setitem(registry._cache, ("llm", registry.mode("llm")), LeakyLLM())
    out = voice.speak(
        "house", "rent", "Jordan only has $310 left.", {800}, "group")
    assert out == voice.SAFE
    assert ("auditor", "fallback") in _trace_pairs()
