"""Stateful in-memory bank ledger seeded from the scenario; balances move on every call."""
from __future__ import annotations

import itertools

from contracts.models import BankTxn, Scenario

from .. import fixtures, registry


class StubNessie:
    def __init__(self) -> None:
        self.seed(fixtures.scenario())

    def seed(self, scenario: Scenario) -> None:
        self._ids = itertools.count(1)
        self._names = {r.id: r.name for r in scenario.roommates}
        self._balance = {r.id: r.checking for r in scenario.roommates}
        self._txns: dict[str, list[BankTxn]] = {r.id: [] for r in scenario.roommates}
        for t in scenario.transactions:
            self._txns[t.roommate_id].append(
                BankTxn(id=t.id, date=t.date, description=t.description, amount=t.amount))

    def _post(self, rid: str, amount: float, description: str) -> str:
        if rid not in self._balance:
            raise KeyError(f"unknown roommate {rid!r}")
        nid = f"stub-{next(self._ids):04d}"
        self._balance[rid] = round(self._balance[rid] + amount, 2)
        self._txns[rid].append(BankTxn(id=nid, date=registry.get("store").today(),
                                       description=description, amount=round(amount, 2)))
        return nid

    def balance(self, rid: str) -> float:
        return self._balance[rid]

    def transactions(self, rid: str) -> list[BankTxn]:
        return sorted(self._txns[rid], key=lambda t: (t.date, t.id), reverse=True)

    def transfer(self, from_rid: str, to_rid: str, amount: float, description: str) -> str:
        nid = self._post(from_rid, -amount, f"Transfer to {self._names[to_rid]}: {description}")
        self._post(to_rid, amount, f"Transfer from {self._names[from_rid]}: {description}")
        return nid

    def pay_bill(self, rid: str, payee: str, amount: float, date: str) -> str:
        return self._post(rid, -amount, f"Bill payment - {payee}")

    def purchase(self, rid: str, merchant: str, amount: float, description: str) -> str:
        return self._post(rid, -amount, f"Purchase - {merchant}: {description}")

    def deposit(self, rid: str, amount: float, description: str) -> str:
        return self._post(rid, amount, description)
