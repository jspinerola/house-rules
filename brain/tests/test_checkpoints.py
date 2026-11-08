"""Integration checkpoints I1 / I4 (REQUIREMENTS.md).

I1 runs in default CI. I4 is opt-in live Nessie (NESSIE_LIVE_TEST=1 + NESSIE_API_KEY).
Report failures; do not patch other modules' code in the checkpoint run.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import fixtures, registry
from app.main import app
from contracts.models import CoverAnswer, Leg, Proposal
from tests.conftest import I1, I4

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _run_live() -> bool:
    return (os.environ.get("NESSIE_LIVE_TEST") or "").strip() == "1" and bool(
        (os.environ.get("NESSIE_API_KEY") or "").strip())


@pytest.fixture
def i1_client(use):
    use(profile=I1)
    c = TestClient(app)
    assert c.post("/demo/reset").json() == {"ok": True}
    return c


def test_I1_health_modes(i1_client):
    h = i1_client.get("/health").json()
    assert h["ok"] is True
    modes = h["modes"]
    assert modes["store"] == "sqlite"
    assert modes["indicators"] == "real"
    assert modes["tools"] == "real"
    for name in ("proposals", "auditor", "personal", "house", "treasurer", "llm", "nessie", "outbox"):
        assert modes[name] == "stub", name


def test_I1_expected_numbers(i1_client):
    """Real Store + Indicators + Tools match expected.json (REQUIREMENTS I1)."""
    tools = registry.get("tools")
    assert tools.split_bill("rent", 2400).shares == {"alex": 800, "sam": 800, "jordan": 800}
    assert tools.split_bill("electric", 150).shares == {"sam": 60, "alex": 45, "jordan": 45}
    assert tools.can_cover("jordan", 800, "2026-11-30") == CoverAnswer(
        level="no", earliest_date="2026-12-15")
    couch = tools.group_affordability("couch", 1200)
    assert couch.plan is not None and couch.plan.months == 3
    assert couch.answers["jordan"] == "tight"

    want = fixtures.expected().indicators["jordan"]
    got = registry.get("indicators").compute("jordan")
    assert got["runway_days"].value == pytest.approx(want["runway_days"].value, abs=0.01)
    assert got["runway_days"].value < 14
    assert registry.get("store").get_roommate("jordan").checking == 310


def test_I1_demo_reset_restores_clock(i1_client):
    assert i1_client.get("/state").json()["today"] == "2026-11-28"
    registry.get("store").set_today("2026-12-16")
    assert i1_client.post("/demo/reset").json() == {"ok": True}
    assert i1_client.get("/state").json()["today"] == "2026-11-28"


@pytest.mark.skipif(not _run_live(), reason="set NESSIE_LIVE_TEST=1 and NESSIE_API_KEY to run I4")
def test_I4_live_nessie_rent_fronting(use):
    """I4 partner smoke: live Nessie + real treasurer; due legs move money in the API."""
    # Auditor stub for partner smoke: real auditor re-reads live balances during
    # announce and can trip on sandbox account recreate; do not patch auditor code here.
    use(profile={**I4, "AUDITOR_MODE": "stub", "OUTBOX_MODE": "stub"})
    c = TestClient(app)
    assert c.post("/demo/reset").json() == {"ok": True}
    h = c.get("/health").json()
    assert h["nessie_mode"] == "live"
    assert h["modes"]["treasurer"] == "real"

    n = registry.get("nessie")
    n.seed(fixtures.scenario())
    assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == (4200, 2600, 310)

    store = registry.get("store")
    p = Proposal(
        id="i4-rent", flow="rent", title="Rent for December",
        required_approvers=["alex", "sam", "jordan"],
        approvals={"alex": "yes", "sam": "yes", "jordan": "yes"}, status="approved",
        legs=[
            Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28"),
            Leg(type="bill_payment", **{"from": "alex"}, payee="Maple Court Apartments",
                amount=2400, date="2026-11-28"),
            Leg(type="scheduled_transfer", **{"from": "jordan"}, to="alex", amount=800,
                date="2026-12-16"),
        ],
    )
    store.save_proposal(p)
    t = registry.get("treasurer")
    ran = t.execute(p.id)
    assert [(l.type, l.amount) for l in ran] == [("transfer", 800), ("bill_payment", 2400)]
    assert all(l.nessie_id for l in ran)
    assert n.balance("sam") == 1800 and n.balance("alex") == 2600 and n.balance("jordan") == 310
    saved = store.get_proposal(p.id)
    assert saved.status == "executed" and saved.legs[2].status == "pending"
    # Live GET confirms sandbox balances moved (I4 done-when). Kevin's scheduled
    # repay stays pending until payday; stub-Nessie contract tests cover run_due.
    assert float(n._request("GET", f"/accounts/{n._accounts['sam']}")["balance"]) == 1800
    assert float(n._request("GET", f"/accounts/{n._accounts['alex']}")["balance"]) == 2600
