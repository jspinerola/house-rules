from contracts.models import Leg, Proposal, TraceEvent, Transaction

from app import registry
from tests.conftest import impl_params


def _proposal(pid: str, approvers=("alex", "sam")) -> Proposal:
    return Proposal(id=pid, flow="rent", title=f"t-{pid}",
                    legs=[Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28")],
                    required_approvers=list(approvers), approvals={r: "pending" for r in approvers})


@impl_params("store", real="sqlite")
def test_store_contract(use, mode):
    use(store=mode)
    s = registry.get("store")
    s.reset()
    assert s.today() == "2026-11-28"
    assert {r.id for r in s.roommates()} == {"alex", "sam", "jordan"}
    assert s.get_roommate("jordan").checking == 310
    assert s.by_handle("sim:sam").id == "sam"
    assert s.by_handle("nobody") is None
    assert s.bill("rent").amount == 2400
    assert s.house_rule("electric").split == {"sam": 0.4}
    assert s.house_rule("rent") is None

    hist = s.transactions("jordan")
    assert len(hist) > 20 and all(t.roommate_id == "jordan" for t in hist)
    assert all(t.date >= "2026-11-01" for t in s.transactions("jordan", since="2026-11-01"))
    s.add_transaction(Transaction(id="x1", roommate_id="jordan", date="2026-11-28",
                                  description="test", category="other", amount=-1))
    assert len(s.transactions("jordan")) == len(hist) + 1

    s.save_proposal(_proposal("p1"))
    s.save_proposal(_proposal("p2"))
    p = s.get_proposal("p1")
    assert p.legs[0].from_ == "sam" and p.approvals == {"alex": "pending", "sam": "pending"}
    assert [x.id for x in s.pending_for("sam")] == ["p1", "p2"]
    p.approvals["sam"] = "yes"
    s.save_proposal(p)
    assert [x.id for x in s.pending_for("sam")] == ["p2"]
    assert [x.id for x in s.proposals()] == ["p1", "p2"]

    for i in range(3):
        s.add_trace(TraceEvent(ts=f"t{i}", agent="house", event="asked", detail=str(i)))
    assert [e.detail for e in s.recent_trace(2)] == ["2", "1"]

    s.set_today("2026-12-16")
    assert s.today() == "2026-12-16"
    s.reset()
    assert s.today() == "2026-11-28" and s.proposals() == [] and s.recent_trace() == []
