"""M4 Proposals: approval state machine (PROPOSALS_MODE=real).

Stub stays "first yes wins" per REQUIREMENTS; multi-approver rules are real-only.
"""
from __future__ import annotations

import pytest

from contracts.models import Leg

from app import fixtures, registry
from tests.conftest import impl_params


def _legs():
    return [Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28"),
            Leg(type="scheduled_transfer", **{"from": "jordan"}, to="alex", amount=800, date="2026-12-16")]


def _rent_fixture_legs():
    return [leg.model_copy() for leg in fixtures.expected().proposals["rent"].legs]


def _use_real(use):
    if not registry.available("proposals", "real"):
        pytest.skip("proposals real not implemented yet")
    use(proposals="real")


def _trace_pairs():
    return [(e.agent, e.event) for e in registry.get("store").recent_trace()]


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
def test_stub_or_real_rent_reaches_executed(use, mode):
    """Done-when shape: with treasurer stubbed, rent ends executed (stub: first yes)."""
    use(proposals=mode)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam", "jordan"])
    assert p.status == "pending" and props.pending()[0].id == p.id
    for rid in ["alex", "sam", "jordan"]:
        props.record_reply(rid, "yes")
    p = props.get(p.id)
    assert p.status == "executed"
    assert [leg.status for leg in p.legs] == ["done", "pending"]
    assert props.record_reply("alex", "yes") is None


def test_create_pending_and_trace(use):
    _use_real(use)
    props = registry.get("proposals")
    p = props.create("rent", "Rent for December", _rent_fixture_legs(), ["alex", "sam", "jordan"])
    assert p.status == "pending"
    assert p.approvals == {"alex": "pending", "sam": "pending", "jordan": "pending"}
    assert props.pending()[0].id == p.id
    assert ("house", "proposed") in _trace_pairs()


def test_partial_yes_stays_pending(use):
    _use_real(use)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam", "jordan"])
    out = props.record_reply("alex", "yes")
    assert out is not None and out.status == "pending"
    assert out.approvals == {"alex": "yes", "sam": "pending", "jordan": "pending"}
    assert all(leg.status == "pending" for leg in props.get(p.id).legs)
    assert ("personal:alex", "approved") in _trace_pairs()
    assert ("house", "approved") not in _trace_pairs()
    assert ("treasurer", "executed") not in _trace_pairs()


def test_all_yes_executes_rent(use):
    _use_real(use)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam", "jordan"])
    assert props.record_reply("alex", "yes").status == "pending"
    assert props.record_reply("sam", "y").status == "pending"
    out = props.record_reply("jordan", "approve")
    assert out.status == "executed"
    assert out.approvals == {"alex": "yes", "sam": "yes", "jordan": "yes"}
    assert [leg.status for leg in out.legs] == ["done", "pending"]
    assert ("house", "approved") in _trace_pairs()
    assert ("treasurer", "executed") in _trace_pairs()


def test_rent_three_legs_from_fixture(use):
    _use_real(use)
    sp = fixtures.expected().proposals["rent"]
    props = registry.get("proposals")
    p = props.create(sp.flow, sp.title, _rent_fixture_legs(), list(sp.required_approvers))
    for rid in sp.required_approvers:
        props.record_reply(rid, "yes")
    p = props.get(p.id)
    assert p.status == "executed"
    assert [(leg.type, leg.amount, leg.status) for leg in p.legs] == [
        ("transfer", 800.0, "done"),
        ("bill_payment", 2400.0, "done"),
        ("scheduled_transfer", 800.0, "pending"),
    ]


def test_any_no_rejects(use):
    _use_real(use)
    props = registry.get("proposals")
    p = props.create("rent", "Rent", _legs(), ["alex", "sam", "jordan"])
    props.record_reply("alex", "yes")
    out = props.record_reply("sam", "nah")
    assert out.status == "rejected"
    assert props.get(p.id).legs[0].status == "pending"
    pairs = _trace_pairs()
    assert ("personal:sam", "declined") in pairs
    assert ("house", "rejected") in pairs
    assert ("treasurer", "executed") not in pairs


def test_oldest_pending_wins(use):
    _use_real(use)
    props = registry.get("proposals")
    older = props.create("rent", "Older", _legs(), ["alex", "sam"])
    newer = props.create("utility", "Newer", [
        Leg(type="transfer", **{"from": "alex"}, to="sam", amount=45, date="2026-11-28"),
    ], ["alex", "sam"])
    out = props.record_reply("alex", "yes")
    assert out.id == older.id
    assert props.get(older.id).approvals["alex"] == "yes"
    assert props.get(newer.id).approvals["alex"] == "pending"


def test_noop_when_no_pending_or_garbage(use):
    _use_real(use)
    props = registry.get("proposals")
    assert props.record_reply("alex", "yes") is None
    props.create("rent", "Rent", _legs(), ["alex", "sam"])
    assert props.record_reply("alex", "maybe later") is None
    assert props.get("p1").approvals["alex"] == "pending"
