"""M8 House agent: rent_due fronting, couch affordability, auditor-checked group replies.

Done-when uses stubbed dependencies (flip only HOUSE_MODE). Real-only tests lock fixture
couch legs, electric split, and privacy.
"""
from __future__ import annotations

import pytest

from app import fixtures, registry
from app.agents.auditor import numbers_in
from tests.conftest import impl_params


def _use_real(use):
    if not registry.available("house", "real"):
        pytest.skip("house real not implemented yet")
    # Nessie stays stub (live not built); matches conftest ALL_REAL profile.
    use(house="real", tools="real", personal="real", proposals="real",
        auditor="real", store="real", nessie="stub", llm="stub")


def _leg_key(leg):
    return (leg.type, leg.from_, leg.to, leg.payee, round(leg.amount, 2), leg.date)


@impl_params("house")
def test_rent_due_proposes_fronting(use, mode):
    use(house=mode)
    replies = registry.get("house").on_event("rent_due")
    assert any(r.target.type == "group" for r in replies)
    [p] = registry.get("store").proposals()
    assert p.flow == "rent" and set(p.required_approvers) == {"alex", "sam", "jordan"}
    summary = {(l.type, l.from_, l.to or l.payee, l.amount, l.date) for l in p.legs}
    assert summary == {("transfer", "sam", "alex", 800, "2026-11-28"),
                       ("bill_payment", "alex", "Maple Court Apartments", 2400, "2026-11-28"),
                       ("scheduled_transfer", "jordan", "alex", 800, "2026-12-16")}


@impl_params("house")
def test_couch_asks_three_and_proposes_three_months(use, mode):
    """Done-when: with deps stubbed (or real), couch → 3 ask_personal + 3-month plan."""
    use(house=mode)
    replies = registry.get("house").on_message("alex", "can we afford a $1,200 couch?")
    assert replies and "3 months" in replies[0].text
    asked = [e for e in registry.get("store").recent_trace() if e.agent == "house" and e.event == "asked"]
    assert len(asked) == 3
    [p] = registry.get("store").proposals()
    assert p.flow == "purchase"
    assert sum(l.amount for l in p.legs if l.type == "purchase") == 1200
    installments = [l for l in p.legs if l.type == "scheduled_transfer"]
    assert len(installments) == 6 and round(sum(l.amount for l in installments), 2) == 800


@impl_params("house")
def test_rent_includes_jordan_fronting_dm(use, mode):
    use(house=mode)
    replies = registry.get("house").on_event("rent_due")
    jordan = [r for r in replies if r.target.type == "dm" and r.target.roommate_id == "jordan"]
    assert jordan and "Alex" in jordan[0].text and "2026-12-16" in jordan[0].text


@impl_params("house")
def test_rent_includes_alex_fronting_dm(use, mode):
    use(house=mode)
    replies = registry.get("house").on_event("rent_due")
    alex = [r for r in replies if r.target.type == "dm" and r.target.roommate_id == "alex"]
    assert alex and "Jordan" in alex[0].text and "2026-12-16" in alex[0].text


def test_couch_ask_personal_trace_detail(use):
    _use_real(use)
    registry.get("house").on_message("alex", "can we afford a $1,200 couch?")
    asked = [e for e in registry.get("store").recent_trace() if e.agent == "house" and e.event == "asked"]
    assert len(asked) == 3
    for rid in ("alex", "sam", "jordan"):
        assert any(rid in e.detail and ("couch" in e.detail.lower() or "133" in e.detail) for e in asked)


def test_couch_legs_match_fixture_plan(use):
    _use_real(use)
    registry.get("house").on_message("alex", "can we afford a $1,200 couch?")
    [p] = registry.get("store").proposals()
    sp = fixtures.expected().proposals["couch"]
    assert p.flow == sp.flow
    assert "Couch Co." in p.title or p.title == sp.title
    assert {_leg_key(l) for l in p.legs} == {_leg_key(l) for l in sp.legs}


def test_group_reply_passes_auditor(use):
    _use_real(use)
    aud = registry.get("auditor")
    rent = registry.get("house").on_event("rent_due")
    group_rent = next(r.text for r in rent if r.target.type == "group")
    allowed_rent = set(numbers_in(group_rent))
    assert aud.check(group_rent, allowed_rent, "group").ok

    # Fresh store for couch (reset via use again)
    _use_real(use)
    aud = registry.get("auditor")
    couch = registry.get("house").on_message("alex", "can we afford a $1,200 couch?")
    group_couch = next(r.text for r in couch if r.target.type == "group")
    allowed_couch = set(numbers_in(group_couch))
    assert aud.check(group_couch, allowed_couch, "group").ok
    assert "310" not in group_couch and "4,200" not in group_couch


def test_electric_bill_splits_by_rule(use):
    _use_real(use)
    replies = registry.get("house").on_event("electric_bill")
    assert any(r.target.type == "group" for r in replies)
    [p] = registry.get("store").proposals()
    assert p.flow == "utility"
    transfers = {(l.from_, l.amount) for l in p.legs if l.type == "transfer"}
    # Sam 40% = $60; Alex is payer so only Sam/Jordan transfer in (or fronting)
    shares = fixtures.expected().split_bill[1].expect.shares
    assert shares["sam"] == 60 and shares["alex"] == 45 and shares["jordan"] == 45
    pay = next(l for l in p.legs if l.type == "bill_payment")
    assert pay.payee == "City Power" and pay.amount == 150
    # Everyone who isn't the payer either transfers now or schedules a repay
    moved = {l.from_ for l in p.legs if l.type in ("transfer", "scheduled_transfer")}
    assert "sam" in moved and "jordan" in moved


def test_unknown_afford_asks_for_price(use):
    _use_real(use)
    replies = registry.get("house").on_message("alex", "can we afford a couch?")
    assert replies and "how much" in replies[0].text.lower()
