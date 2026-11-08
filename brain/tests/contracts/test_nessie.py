import pytest

from app import registry


@pytest.mark.parametrize("mode", ["stub", pytest.param("live", marks=pytest.mark.skip(
    reason="live Nessie lands in D2; never called from the skeleton"))])
def test_nessie_contract(use, mode):
    use(nessie=mode)
    n = registry.get("nessie")
    assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == (4200, 2600, 310)
    tid = n.transfer("sam", "alex", 800, "rent share")
    assert tid and n.balance("sam") == 1800 and n.balance("alex") == 5000
    n.pay_bill("alex", "Maple Court Apartments", 2400, "2026-11-28")
    n.purchase("alex", "Couch Co.", 1200, "couch")
    n.deposit("jordan", 1350, "Payroll")
    assert n.balance("alex") == 1400 and n.balance("jordan") == 1660
    newest = n.transactions("alex")[0]
    assert newest.date == "2026-11-28" and newest.amount in (-2400, -1200, 800)
    dates = [t.date for t in n.transactions("alex")]
    assert dates == sorted(dates, reverse=True)
