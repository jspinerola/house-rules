"""In-memory Store loaded from fixtures/scenario.json."""
from __future__ import annotations

from contracts.models import Bill, HouseRule, Proposal, Roommate, TraceEvent, Transaction

from .. import fixtures


class StubStore:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        s = fixtures.scenario()
        self._today = s.today
        self._roommates = {r.id: r for r in s.roommates}
        self._txns: list[Transaction] = list(s.transactions)
        self._bills = {b.type: b for b in s.bills}
        self._rules = {r.bill_type: r for r in s.house_rules}
        self._proposals: dict[str, Proposal] = {}
        self._trace: list[TraceEvent] = []

    def get_roommate(self, rid: str) -> Roommate:
        if rid not in self._roommates:
            raise KeyError(f"unknown roommate {rid!r}")
        return self._roommates[rid]

    def by_handle(self, handle: str) -> Roommate | None:
        return next((r for r in self._roommates.values() if r.handle == handle), None)

    def roommates(self) -> list[Roommate]:
        return list(self._roommates.values())

    def transactions(self, rid: str, since: str | None = None) -> list[Transaction]:
        return [t for t in self._txns if t.roommate_id == rid and (since is None or t.date >= since)]

    def add_transaction(self, txn: Transaction) -> None:
        self._txns.append(txn)

    def bill(self, bill_type: str) -> Bill:
        return self._bills[bill_type]

    def house_rule(self, bill_type: str) -> HouseRule | None:
        return self._rules.get(bill_type)

    def save_proposal(self, p: Proposal) -> None:
        self._proposals[p.id] = p.model_copy(deep=True)

    def get_proposal(self, pid: str) -> Proposal:
        if pid not in self._proposals:
            raise KeyError(f"unknown proposal {pid!r}")
        return self._proposals[pid].model_copy(deep=True)

    def proposals(self) -> list[Proposal]:
        return [p.model_copy(deep=True) for p in self._proposals.values()]

    def pending_for(self, rid: str) -> list[Proposal]:
        return [p for p in self.proposals()
                if p.status == "pending" and p.approvals.get(rid) == "pending"]

    def add_trace(self, e: TraceEvent) -> None:
        self._trace.append(e)

    def recent_trace(self, n: int = 50) -> list[TraceEvent]:
        return list(reversed(self._trace[-n:]))

    def today(self) -> str:
        return self._today

    def set_today(self, d: str) -> None:
        self._today = d
