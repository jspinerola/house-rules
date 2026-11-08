"""Rigid isolation/determinism tests for Tools (TOOLS_MODE=real).

Pure math only — no LLM. Cover answers must never expose balances.
REQUIREMENTS M3 done-when: Store and Indicators stubbed.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import registry
from contracts.models import CoverAnswer


@pytest.fixture
def tools(use):
    use(tools="real", store="stub", indicators="stub", nessie="stub")
    return registry.get("tools")


def test_expected_with_store_and_indicators_stubbed(tools):
    assert tools.split_bill("rent", 2400).shares == {"alex": 800, "sam": 800, "jordan": 800}
    jordan = tools.can_cover("jordan", 800, "2026-11-30")
    assert jordan == CoverAnswer(level="no", earliest_date="2026-12-15")
    assert tools.split_bill("electric", 150).shares == {"sam": 60, "alex": 45, "jordan": 45}
    couch = tools.group_affordability("couch", 1200)
    assert couch.plan is not None and couch.plan.months == 3
    assert couch.answers["jordan"] == "tight"
    assert tools.payday_plan("jordan", 800).fronter == "alex"


def test_deterministic_across_calls(tools):
    a = tools.can_cover("jordan", 800, "2026-11-30")
    b = tools.can_cover("jordan", 800, "2026-11-30")
    assert a == b
    assert tools.split_bill("rent", 2400) == tools.split_bill("rent", 2400)
    assert tools.payday_plan("jordan", 800) == tools.payday_plan("jordan", 800)
    assert tools.group_affordability("couch", 1200) == tools.group_affordability("couch", 1200)


def test_can_cover_only_uses_that_roommate_balance(tools):
    before = tools.can_cover("jordan", 800, "2026-11-30")
    # Drain Xander's ledger; Kevin's cover must not move.
    registry.get("nessie").purchase("alex", "Poison Co", 4000, "isolation probe")
    after = tools.can_cover("jordan", 800, "2026-11-30")
    assert after == before
    assert tools.can_cover("alex", 800, "2026-11-30").level == "no"


def test_cover_answer_exposes_no_balances(tools):
    for rid, amount in (("alex", 800), ("jordan", 800), ("jordan", 133.33)):
        dump = tools.can_cover(rid, amount, "2026-11-30").model_dump()
        assert set(dump) <= {"level", "earliest_date", "reason"}  # reason is a code, never a figure
        blob = repr(dump).lower()
        assert "balance" not in blob and "income" not in blob
        assert "4200" not in blob and "2600" not in blob and "310" not in blob


def test_payday_plan_fronter_never_debtor(tools):
    plan = tools.payday_plan("jordan", 800)
    assert plan.fronter != "jordan"
    assert plan.fronter == "alex"
    payday = tools.next_payday("jordan", registry.get("store").today())
    assert plan.repay_date == (date.fromisoformat(payday) + timedelta(days=1)).isoformat()


def test_unknown_roommate_raises(tools):
    for bad in ("nobody", "jordan'; DROP--", "alex' OR '1'='1"):
        with pytest.raises(KeyError):
            tools.can_cover(bad, 1, "2026-11-30")
        with pytest.raises(KeyError):
            tools.payday_plan(bad, 1)
        with pytest.raises(KeyError):
            tools.next_payday(bad, "2026-11-28")
        with pytest.raises(KeyError):
            tools.buffer_after(bad, 1)


def test_split_shares_sum_to_amount(tools):
    for bill_type, amount in (("rent", 2400), ("electric", 150), ("water", 100)):
        shares = tools.split_bill(bill_type, amount).shares
        assert round(sum(shares.values()), 2) == amount
        assert set(shares) == {"alex", "sam", "jordan"}


def test_cover_thresholds(tools):
    # Xander $4200, no payday credited when by == today before Dec 1.
    today = registry.get("store").today()
    assert tools.can_cover("alex", 4000, today).level == "ok"       # 200 left
    assert tools.can_cover("alex", 4100, today).level == "tight"    # 100 left
    assert tools.can_cover("alex", 4300, today).level == "no"       # negative


def test_group_affordability_never_picks_plan_with_no(tools):
    got = tools.group_affordability("couch", 1200)
    assert got.plan is not None
    assert "no" not in got.answers.values()
    assert got.plan.months == 3
    assert got.answers == {"alex": "ok", "sam": "ok", "jordan": "tight"}


def test_group_affordability_rejects_negative_price(tools):
    with pytest.raises(ValueError):
        tools.group_affordability("couch", -1)
    with pytest.raises(ValueError):
        tools.group_affordability("couch", float("nan"))


def test_can_cover_rejects_negative_amount_and_bad_date(tools):
    with pytest.raises(ValueError):
        tools.can_cover("alex", -1, "2026-11-30")
    with pytest.raises(ValueError):
        tools.can_cover("alex", float("inf"), "2026-11-30")
    with pytest.raises(ValueError, match="date"):
        tools.can_cover("alex", 1, "not-a-date")
    with pytest.raises(ValueError, match="date"):
        tools.next_payday("alex", "11/28/2026")


def test_works_with_sqlite_store(use):
    use(tools="real", store="sqlite", indicators="stub", nessie="stub")
    registry.get("store").reset()
    t = registry.get("tools")
    assert t.split_bill("rent", 2400).shares["jordan"] == 800
    assert t.can_cover("jordan", 800, "2026-11-30") == CoverAnswer(
        level="no", earliest_date="2026-12-15")
    assert t.group_affordability("couch", 1200).plan.months == 3
