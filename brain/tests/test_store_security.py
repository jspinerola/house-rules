"""Rigid isolation/integrity tests for SqliteStore (DB_MODE=sqlite)."""
from __future__ import annotations

import sqlite3

import pytest

from app import registry
from app.db import SqliteStore, TABLES
from contracts.models import Leg, Proposal, TraceEvent, Transaction


def _proposal(
    pid: str,
    approvers: tuple[str, ...] = ("alex", "sam", "jordan"),
    legs: list[Leg] | None = None,
) -> Proposal:
    if legs is None:
        legs = [
            Leg(type="transfer", **{"from": "sam"}, to="alex", amount=800, date="2026-11-28"),
            Leg(type="transfer", **{"from": "jordan"}, to="alex", amount=800, date="2026-11-28"),
            Leg(type="bill_payment", **{"from": "alex"}, payee="Maple Court", amount=2400,
                date="2026-11-28"),
        ]
    return Proposal(
        id=pid, flow="rent", title=f"t-{pid}", legs=legs,
        required_approvers=list(approvers),
        approvals={r: "pending" for r in approvers},
    )


@pytest.fixture
def store(use) -> SqliteStore:
    use(store="sqlite")
    s = registry.get("store")
    assert isinstance(s, SqliteStore)
    s.reset()
    return s


# ----- isolation -----

def test_transactions_scoped_to_roommate(store):
    jordan = store.transactions("jordan")
    assert jordan and all(t.roommate_id == "jordan" for t in jordan)
    alex_ids = {t.id for t in store.transactions("alex")}
    sam_ids = {t.id for t in store.transactions("sam")}
    jordan_ids = {t.id for t in jordan}
    assert jordan_ids.isdisjoint(alex_ids)
    assert jordan_ids.isdisjoint(sam_ids)
    # since filter narrows; never widens to other roommates
    since = store.transactions("jordan", since="2026-11-01")
    assert all(t.roommate_id == "jordan" and t.date >= "2026-11-01" for t in since)
    assert len(since) <= len(jordan)


def test_pending_for_only_that_approver(store):
    store.save_proposal(_proposal("p-all"))
    store.save_proposal(_proposal("p-alex-sam", approvers=("alex", "sam")))
    assert [p.id for p in store.pending_for("jordan")] == ["p-all"]
    assert [p.id for p in store.pending_for("sam")] == ["p-all", "p-alex-sam"]

    p = store.get_proposal("p-all")
    p.approvals["sam"] = "yes"
    store.save_proposal(p)
    assert [x.id for x in store.pending_for("sam")] == ["p-alex-sam"]
    assert "p-all" in [x.id for x in store.pending_for("jordan")]


def test_get_roommate_unknown_raises(store):
    with pytest.raises(KeyError):
        store.get_roommate("jord")
    with pytest.raises(KeyError):
        store.get_roommate("alex' OR '1'='1")


def test_by_handle_exact_only(store):
    assert store.by_handle("sim:sam").id == "sam"
    for bad in ("sim:sam' OR '1'='1", "sim:%", "sim:sa", "SIM:sam", "sim:sam "):
        assert store.by_handle(bad) is None


# ----- integrity -----

def test_foreign_keys_reject_orphan_transaction(store):
    assert store._db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    orphan = Transaction(
        id="orphan-1", roommate_id="nobody", date="2026-11-28",
        description="bad", category="other", amount=-1,
    )
    with pytest.raises(sqlite3.IntegrityError):
        store.add_transaction(orphan)
    assert all(t.id != "orphan-1" for t in store.transactions("jordan"))


def test_save_proposal_replaces_legs_and_approvals(store):
    store.save_proposal(_proposal("p1"))
    assert len(store.get_proposal("p1").legs) == 3
    assert set(store.get_proposal("p1").required_approvers) == {"alex", "sam", "jordan"}

    slim = _proposal(
        "p1",
        approvers=("alex",),
        legs=[Leg(type="transfer", **{"from": "alex"}, to="sam", amount=1, date="2026-11-28")],
    )
    store.save_proposal(slim)
    p = store.get_proposal("p1")
    assert len(p.legs) == 1 and p.legs[0].amount == 1
    assert p.required_approvers == ["alex"] and p.approvals == {"alex": "pending"}

    legs = store._q("SELECT COUNT(*) AS n FROM legs WHERE proposal_id = ?", ("p1",))[0]["n"]
    appr = store._q("SELECT COUNT(*) AS n FROM approvals WHERE proposal_id = ?", ("p1",))[0]["n"]
    assert legs == 1 and appr == 1


def test_reset_wipes_sensitive_state(store):
    store.save_proposal(_proposal("p1"))
    store.add_transaction(Transaction(
        id="extra-1", roommate_id="jordan", date="2026-11-28",
        description="extra", category="other", amount=-5,
    ))
    store.add_trace(TraceEvent(ts="t0", agent="house", event="asked", detail="x"))
    store.set_today("2026-12-16")

    store.reset()
    assert store.today() == "2026-11-28"
    assert store.proposals() == []
    assert store.recent_trace() == []
    assert store.get_roommate("alex").checking == 4200
    assert store.get_roommate("sam").checking == 2600
    assert store.get_roommate("jordan").checking == 310
    assert all(t.id != "extra-1" for t in store.transactions("jordan"))


def test_recent_trace_newest_first_capped(store):
    for i in range(60):
        store.add_trace(TraceEvent(ts=f"t{i:02d}", agent="house", event="asked", detail=str(i)))
    recent = store.recent_trace(50)
    assert len(recent) == 50
    assert [e.detail for e in recent] == [str(i) for i in range(59, 9, -1)]


def test_proposals_oldest_first(store):
    store.save_proposal(_proposal("p1", approvers=("sam",)))
    store.save_proposal(_proposal("p2", approvers=("sam",)))
    store.save_proposal(_proposal("p3", approvers=("sam",)))
    assert [p.id for p in store.proposals()] == ["p1", "p2", "p3"]
    assert [p.id for p in store.pending_for("sam")] == ["p1", "p2", "p3"]


def test_duplicate_transaction_id_rejected(store):
    txn = Transaction(
        id="dup-1", roommate_id="jordan", date="2026-11-28",
        description="once", category="other", amount=-1,
    )
    store.add_transaction(txn)
    with pytest.raises(sqlite3.IntegrityError):
        store.add_transaction(txn)
    assert sum(1 for t in store.transactions("jordan") if t.id == "dup-1") == 1


def test_seed_balances_match_scenario(store):
    assert store.get_roommate("alex").checking == 4200
    assert store.get_roommate("sam").checking == 2600
    assert store.get_roommate("jordan").checking == 310
    assert store.today() == "2026-11-28"
    assert store.bill("rent").amount == 2400


# ----- injection / abuse -----

def test_parameterized_lookups_ignore_sql_meta(store):
    payloads = (
        "'; DROP TABLE roommates;--",
        "rent'; DROP TABLE bills;--",
        "sim:sam'; DROP TABLE transactions;--",
        "2026-11-01'; DROP TABLE trace;--",
    )
    for payload in payloads:
        with pytest.raises(KeyError):
            store.get_proposal(payload)
        with pytest.raises(KeyError):
            store.bill(payload)
        assert store.house_rule(payload) is None
        assert store.by_handle(payload) is None
        # since is a filter value; must not widen or destroy schema
        store.transactions("jordan", since=payload)

    for table in TABLES:
        row = store._q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,))
        assert row, f"table {table} missing after injection payloads"


def test_tmp_db_isolation(tmp_path, monkeypatch):
    path_a = str(tmp_path / "a.db")
    path_b = str(tmp_path / "b.db")
    monkeypatch.setenv("SQLITE_PATH", path_a)
    registry.reset()
    a = SqliteStore(path_a)
    a.reset()
    a.save_proposal(_proposal("only-a", approvers=("alex",)))
    a.add_trace(TraceEvent(ts="t", agent="house", event="asked", detail="a"))

    b = SqliteStore(path_b)
    b.reset()
    assert b.proposals() == []
    assert b.recent_trace() == []
    assert [p.id for p in a.proposals()] == ["only-a"]
    assert [e.detail for e in a.recent_trace()] == ["a"]
