from contracts.models import Leg

from app import registry
from tests.conftest import impl_params


def _legs():
    return [Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28"),
            Leg(type="scheduled_transfer", **{"from": "jordan"}, to="alex", amount=800, date="2026-12-16")]


@impl_params("proposals")
def test_parse(use, mode):
    use(proposals=mode)
    p = registry.get("proposals")
    for t in ["yes", "Y", "yep", "ok", "approve", "\U0001F44D", "Yes!"]:
        assert p.parse(t) == "yes", t
    for t in ["no", "N", "nah", "cancel"]:
        assert p.parse(t) == "no", t
    assert p.parse("can we afford a couch?") is None


@impl_params("proposals")
def test_rent_walks_pending_to_executed(use, mode):
    use(proposals=mode)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam", "jordan"])
    assert p.status == "pending" and props.pending()[0].id == p.id
    for rid in ["alex", "sam", "jordan"]:
        props.record_reply(rid, "yes")
    p = props.get(p.id)
    assert p.status == "executed"
    assert [leg.status for leg in p.legs] == ["done", "pending"]
    assert props.record_reply("alex", "yes") is None  # nothing pending any more


@impl_params("proposals")
def test_no_rejects(use, mode):
    use(proposals=mode)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam"])
    assert props.record_reply("sam", "nah").status == "rejected"
    assert props.get(p.id).legs[0].status == "pending"


def test_real_needs_every_yes(use):
    if not registry.available("proposals", "real"):
        import pytest
        pytest.skip("proposals real not implemented yet")
    use(proposals="real")
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam"])
    assert props.record_reply("alex", "yes").status == "pending"
    assert props.record_reply("sam", "y").status == "executed"
    assert props.get(p.id).approvals == {"alex": "yes", "sam": "yes"}
