import pytest

from contracts.models import Leg

from app import registry
from tests.conftest import impl_params


def _approved_rent() -> str:
    store = registry.get("store")
    from contracts.models import Proposal
    p = Proposal(id="p1", flow="rent", title="Rent for December", required_approvers=["alex", "sam", "jordan"],
                 approvals={"alex": "yes", "sam": "yes", "jordan": "yes"}, status="approved", legs=[
                     Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28"),
                     Leg(type="bill_payment", **{"from": "alex"}, payee="Maple Court Apartments",
                         amount=2400, date="2026-11-28"),
                     Leg(type="scheduled_transfer", **{"from": "jordan"}, to="alex", amount=800,
                         date="2026-12-16")])
    store.save_proposal(p)
    return p.id


@impl_params("treasurer")
def test_refuses_unapproved(use, mode):
    use(treasurer=mode)
    pid = _approved_rent()
    store = registry.get("store")
    p = store.get_proposal(pid)
    p.status = "pending"
    store.save_proposal(p)
    with pytest.raises(ValueError):
        registry.get("treasurer").execute(pid)
    assert registry.get("nessie").balance("alex") == 4200


@impl_params("treasurer")
def test_rent_with_fronting(use, mode):
    use(treasurer=mode)
    pid = _approved_rent()
    t, n = registry.get("treasurer"), registry.get("nessie")
    ran = t.execute(pid)
    assert [(l.type, l.amount) for l in ran] == [("transfer", 800), ("bill_payment", 2400)]
    assert all(l.nessie_id for l in ran)
    assert n.balance("alex") == 2600 and n.balance("sam") == 1800 and n.balance("jordan") == 310
    p = registry.get("store").get_proposal(pid)
    assert p.status == "executed" and p.legs[2].status == "pending"
    assert t.run_due("2026-12-15") == []
    [late] = t.run_due("2026-12-16")
    assert (late.from_, late.to, late.amount, late.status) == ("jordan", "alex", 800, "done")
    assert n.balance("alex") == 3400
    assert registry.get("outbox").sent  # confirmation pushed to the group


def test_real_marks_failed_on_nessie_error(use, monkeypatch):
    if not registry.available("treasurer", "real"):
        pytest.skip("treasurer real not implemented yet")
    from contracts.interfaces import NessieError
    use(treasurer="real")
    pid = _approved_rent()
    n = registry.get("nessie")

    def boom(*a, **k):
        raise NessieError("sandbox down")
    monkeypatch.setattr(n, "pay_bill", boom)
    ran = registry.get("treasurer").execute(pid)
    p = registry.get("store").get_proposal(pid)
    assert [l.type for l in ran] == ["transfer"]
    assert p.status == "failed" and p.legs[1].status == "failed" and p.legs[2].status == "pending"
    assert "failed" in registry.get("outbox").sent[-1].text


def test_live_nessie_refuses(use):
    use(nessie="live")
    with pytest.raises(NotImplementedError):
        registry.get("nessie")
