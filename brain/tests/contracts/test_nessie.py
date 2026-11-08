import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from app import fixtures, registry

# Match brain/app/main.py: local .env supplies the key without overriding a real env.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def _run_live() -> bool:
    """Live hits the real Nessie sandbox; opt in with NESSIE_LIVE_TEST=1 + API key."""
    return (os.environ.get("NESSIE_LIVE_TEST") or "").strip() == "1" and bool(
        (os.environ.get("NESSIE_API_KEY") or "").strip())


@pytest.mark.parametrize("mode", [
    "stub",
    pytest.param("live", marks=pytest.mark.skipif(
        not _run_live(), reason="set NESSIE_LIVE_TEST=1 and NESSIE_API_KEY to run live")),
])
def test_nessie_contract(use, mode):
    use(nessie=mode, store="stub")
    n = registry.get("nessie")
    n.seed(fixtures.scenario())
    assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == (4200, 2600, 310)
    tid = n.transfer("sam", "alex", 800, "rent share")
    assert tid and n.balance("sam") == 1800 and n.balance("alex") == 5000
    n.pay_bill("alex", "Maple Court Apartments", 2400, "2026-11-28")
    n.purchase("alex", "Couch Co.", 1200, "couch")
    n.deposit("jordan", 1350, "Payroll")
    assert n.balance("alex") == 1400 and n.balance("jordan") == 1660
    newest = n.transactions("alex")[0]
    assert newest.date and newest.amount in (-2400, -1200, 800)
    dates = [t.date for t in n.transactions("alex")]
    assert dates == sorted(dates, reverse=True)

    if mode == "live":
        # Cents survive in the ledger; the sandbox account shows the floored dollars.
        n.transfer("sam", "alex", 133.33, "couch")
        assert (n.balance("alex"), n.balance("sam")) == (1533.33, 1666.67)
        for rid in ("alex", "sam", "jordan"):
            live = n._request("GET", f"/accounts/{n._accounts[rid]}")["balance"]
            assert live == int(n.balance(rid) // 1), (rid, live, n.balance(rid))
