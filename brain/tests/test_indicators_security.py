"""Rigid isolation/determinism tests for Indicators (INDICATORS_MODE=real).

Code does the math; no LLM. Each compute(rid) may only use that roommate's
accounts/history plus shared house facts (rent share, clock).
"""
from __future__ import annotations

from datetime import date

import pytest

from app import fixtures, registry
from contracts.models import Transaction

KEYS = {
    "emergency_fund_months", "debt_to_income", "savings_rate", "credit_utilization",
    "net_worth", "debt_to_asset", "housing_cost_ratio", "liquidity_ratio",
    "runway_days", "rent_to_income", "days_to_payday", "buffer_after",
}
@pytest.fixture
def indicators(use):
    """Real indicators on stub store/nessie/tools (REQUIREMENTS M2 done-when)."""
    use(indicators="real", store="stub", nessie="stub", tools="real")
    return registry.get("indicators")


def test_compute_returns_exactly_twelve_keys(indicators):
    for rid in ("alex", "sam", "jordan"):
        got = indicators.compute(rid)
        assert set(got) == KEYS
        for ind in got.values():
            assert ind.status in ("good", "watch", "risk")
            assert isinstance(ind.value, float)
            assert ind.value == ind.value  # not NaN
            assert ind.value != float("inf")


def test_matches_expected_with_store_stubbed(indicators):
    want = fixtures.expected().indicators
    for rid in ("alex", "sam", "jordan"):
        got = indicators.compute(rid)
        for k in KEYS:
            assert got[k].value == pytest.approx(want[rid][k].value, abs=0.01), f"{rid}.{k}"
            assert got[k].status == want[rid][k].status, f"{rid}.{k}"


def test_jordan_runway_risk_under_fourteen(indicators):
    ind = indicators.compute("jordan")
    assert ind["runway_days"].value < 14
    assert ind["runway_days"].status == "risk"
    assert ind["buffer_after"].value < 0
    assert ind["buffer_after"].inputs["amount"] == 800.0


def test_unknown_roommate_raises(indicators):
    with pytest.raises(KeyError):
        indicators.compute("nobody")
    with pytest.raises(KeyError):
        indicators.compute("jordan'; DROP TABLE--")


def test_isolation_other_roommate_txns_do_not_change_result(indicators):
    before = indicators.compute("jordan")
    store = registry.get("store")
    # Poison Xander's history with a huge spend; Kevin must be unchanged.
    store.add_transaction(Transaction(
        id="alex-poison", roommate_id="alex", date="2026-11-27",
        description="poison", category="other", amount=-50_000,
    ))
    after = indicators.compute("jordan")
    for k in KEYS:
        assert after[k].value == pytest.approx(before[k].value, abs=1e-9), k
        assert after[k].status == before[k].status, k


def test_inputs_never_leak_other_roommates(indicators):
    others = {"alex", "sam", "jordan"}
    for rid in ("alex", "sam", "jordan"):
        got = indicators.compute(rid)
        foreign = others - {rid}
        for key, ind in got.items():
            blob = repr(ind.inputs).lower()
            for other in foreign:
                assert other not in blob, f"{rid}.{key} inputs leak {other}: {ind.inputs}"
            # personal balance inputs must match that roommate only
            if "balance" in ind.inputs:
                assert ind.inputs["balance"] == pytest.approx(
                    registry.get("nessie").balance(rid), abs=0.01)


def test_house_metric_formulas(indicators):
    store, nessie, tools = registry.get("store"), registry.get("nessie"), registry.get("tools")
    today = store.today()
    for rid in ("alex", "sam", "jordan"):
        got = indicators.compute(rid)
        balance = nessie.balance(rid)
        r = store.get_roommate(rid)
        txns = store.transactions(rid)
        months = sorted({t.date[:7] for t in txns})
        n = max(len(months), 1)
        spend = round(-sum(t.amount for t in txns if t.amount < 0 and t.category != "debt_payments") / n, 2)
        share = tools.split_bill("rent", store.bill("rent").amount).shares[rid]
        payday = tools.next_payday(rid, today)
        days = float((date.fromisoformat(payday) - date.fromisoformat(today)).days)
        runway = round(balance / (spend / 30), 1) if spend else float("inf")
        buffer = round(balance - share, 2)

        assert got["runway_days"].value == pytest.approx(runway, abs=0.01)
        assert got["runway_days"].inputs["balance"] == pytest.approx(balance, abs=0.01)
        assert got["runway_days"].inputs["avg_monthly_spending"] == pytest.approx(spend, abs=0.01)
        assert got["rent_to_income"].value == pytest.approx(round(share / r.monthly_income, 4), abs=1e-4)
        assert got["days_to_payday"].value == days
        assert got["days_to_payday"].inputs["next_payday"] == payday
        assert got["buffer_after"].value == pytest.approx(buffer, abs=0.01)
        assert got["buffer_after"].inputs["amount"] == pytest.approx(share, abs=0.01)


def test_status_thresholds_runway_and_buffer(indicators):
    """Lock SPEC/workshop thresholds used by the house extras."""
    from wellness.metrics import _status

    assert _status(30, 30, 14) == "good"
    assert _status(20, 30, 14) == "watch"
    assert _status(7, 30, 14) == "risk"
    assert _status(200, 200, 0) == "good"
    assert _status(50, 200, 0) == "watch"
    assert _status(-490, 200, 0) == "risk"
    assert _status(0.25, 0.3, 0.4, False) == "good"
    assert _status(0.35, 0.3, 0.4, False) == "watch"
    assert _status(0.4571, 0.3, 0.4, False) == "risk"


def test_deterministic_across_calls(indicators):
    a = indicators.compute("sam")
    b = indicators.compute("sam")
    for k in KEYS:
        assert a[k].value == b[k].value
        assert a[k].status == b[k].status
        assert a[k].inputs == b[k].inputs


def test_works_with_sqlite_store(use):
    use(indicators="real", store="sqlite", nessie="stub", tools="real")
    registry.get("store").reset()
    ind = registry.get("indicators")
    got = ind.compute("jordan")
    assert set(got) == KEYS
    assert got["runway_days"].value < 14
    want = fixtures.expected().indicators["jordan"]
    for k in KEYS:
        assert got[k].value == pytest.approx(want[k].value, abs=0.01), k


def test_missing_payday_raises(use, monkeypatch):
    use(indicators="real", store="stub", nessie="stub", tools="real")
    tools = registry.get("tools")
    monkeypatch.setattr(tools, "next_payday", lambda rid, after: None)
    with pytest.raises(ValueError, match="next payday"):
        registry.get("indicators").compute("jordan")
