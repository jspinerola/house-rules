"""Rigid approval/schedule/privacy tests for Treasurer (TREASURER_MODE=real).

Only approved legs may move money via Nessie. Failures stop closed. Group
confirmations stay auditor-safe. REQUIREMENTS M10 done-when: Nessie stubbed.
"""
from __future__ import annotations

import pytest

from app import fixtures, registry
from contracts.interfaces import NessieError
from contracts.models import AuditResult, Leg, Proposal


def _rent(status: str = "approved", amounts: tuple[float, float, float] = (800, 2400, 800)) -> str:
    a0, a1, a2 = amounts
    p = Proposal(
        id="p-rent", flow="rent", title="Rent for December",
        required_approvers=["alex", "sam", "jordan"],
        approvals={"alex": "yes", "sam": "yes", "jordan": "yes"}, status=status,
        legs=[
            Leg(type="transfer", **{"from": "sam"}, to="alex", amount=a0, date="2026-11-28"),
            Leg(type="bill_payment", **{"from": "alex"}, payee="Maple Court Apartments",
                amount=a1, date="2026-11-28"),
            Leg(type="scheduled_transfer", **{"from": "jordan"}, to="alex", amount=a2,
                date="2026-12-16"),
        ],
    )
    registry.get("store").save_proposal(p)
    return p.id


@pytest.fixture
def treasurer(use):
    use(treasurer="real", nessie="stub", store="stub", auditor="stub", outbox="stub")
    registry.get("nessie").seed(fixtures.scenario())
    registry.get("store").reset()
    return registry.get("treasurer")


def test_execute_requires_approved(treasurer):
    n = registry.get("nessie")
    for status in ("pending", "rejected", "executed", "failed"):
        pid = _rent(status=status)
        before = (n.balance("alex"), n.balance("sam"), n.balance("jordan"))
        with pytest.raises(ValueError, match="approved"):
            treasurer.execute(pid)
        assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == before


def test_unknown_proposal_raises(treasurer):
    with pytest.raises(KeyError):
        treasurer.execute("no-such-proposal")


def test_rent_fronting_schedule_with_nessie_stubbed(treasurer):
    pid = _rent()
    t, n = treasurer, registry.get("nessie")
    ran = t.execute(pid)
    assert [(l.type, l.amount) for l in ran] == [("transfer", 800), ("bill_payment", 2400)]
    assert all(l.nessie_id for l in ran)
    assert n.balance("alex") == 2600 and n.balance("sam") == 1800 and n.balance("jordan") == 310
    p = registry.get("store").get_proposal(pid)
    assert p.status == "executed" and p.legs[2].status == "pending"
    [late] = t.run_due("2026-12-16")
    assert (late.from_, late.to, late.amount, late.status) == ("jordan", "alex", 800, "done")
    assert n.balance("alex") == 3400


def test_run_due_before_date_is_noop(treasurer):
    pid = _rent()
    t, n = treasurer, registry.get("nessie")
    t.execute(pid)
    assert t.run_due("2026-12-15") == []
    assert n.balance("jordan") == 310
    assert registry.get("store").get_proposal(pid).legs[2].status == "pending"


def test_rejects_non_positive_leg_amount(treasurer):
    n = registry.get("nessie")
    before = (n.balance("alex"), n.balance("sam"), n.balance("jordan"))
    for bad in (0.0, -1.0):
        pid = _rent(amounts=(bad, 2400, 800))
        with pytest.raises(ValueError):
            treasurer.execute(pid)
        assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == before


def test_nessie_error_stops_later_legs(treasurer, monkeypatch):
    pid = _rent()
    n = registry.get("nessie")

    def boom(*a, **k):
        raise NessieError("sandbox down")

    monkeypatch.setattr(n, "pay_bill", boom)
    ran = treasurer.execute(pid)
    p = registry.get("store").get_proposal(pid)
    assert [l.type for l in ran] == ["transfer"]
    assert p.status == "failed"
    assert p.legs[0].status == "done" and p.legs[1].status == "failed" and p.legs[2].status == "pending"
    assert "failed" in registry.get("outbox").sent[-1].text.lower()


def test_failed_proposal_run_due_does_not_retry_failed_leg(treasurer, monkeypatch):
    pid = _rent()
    n = registry.get("nessie")
    calls = {"pay_bill": 0}

    def boom(*a, **k):
        calls["pay_bill"] += 1
        raise NessieError("sandbox down")

    monkeypatch.setattr(n, "pay_bill", boom)
    treasurer.execute(pid)
    assert calls["pay_bill"] == 1
    assert treasurer.run_due("2026-12-16") == []
    assert calls["pay_bill"] == 1
    p = registry.get("store").get_proposal(pid)
    assert p.status == "failed" and p.legs[1].status == "failed"


def test_trace_records_executed_legs(treasurer):
    pid = _rent()
    treasurer.execute(pid)
    events = registry.get("store").recent_trace(50)
    treas = [e for e in events if e.agent == "treasurer" and e.event == "executed"]
    assert len(treas) >= 2
    blob = " ".join(e.detail for e in treas)
    assert "800" in blob and "2,400" in blob and "nessie" in blob


def test_group_confirmation_has_no_balances(use):
    use(treasurer="real", nessie="stub", store="stub", auditor="real", outbox="stub")
    registry.get("nessie").seed(fixtures.scenario())
    registry.get("store").reset()
    registry.get("treasurer").execute(_rent())
    texts = [r.text.lower() for r in registry.get("outbox").sent]
    blob = " ".join(texts)
    assert "4200" not in blob and "2600" not in blob and "310" not in blob
    assert "balance" not in blob and "income" not in blob
    assert any("800" in text or "2,400" in text or "2400" in text for text in texts)


def test_auditor_block_uses_safe_fallback(treasurer, monkeypatch):
    pid = _rent()
    monkeypatch.setattr(
        registry.get("auditor"), "check",
        lambda text, allowed_numbers, audience: AuditResult(ok=False, reasons=["blocked"]),
    )
    treasurer.execute(pid)
    last = registry.get("outbox").sent[-1].text.lower()
    assert "house view" in last
    assert "4200" not in last and "balance" not in last
