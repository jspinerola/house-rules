"""Treasurer (TREASURER_MODE=real): the only module that calls Nessie write endpoints.

execute(pid) refuses unless the proposal is approved, runs legs dated today or earlier,
leaves future legs pending for run_due, records Nessie ids, traces, and posts a group
confirmation through the Outbox (after the Auditor checks it).
"""
from __future__ import annotations

import math

from contracts.interfaces import NessieError
from contracts.models import GroupTarget, Leg, Proposal, Reply

from . import registry, trace
from .fmt import money


def _valid_amount(amount: float) -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
        raise ValueError("leg amount must be a finite number")
    if amount <= 0:
        raise ValueError("leg amount must be > 0")
    return float(amount)


class Treasurer:
    def _names(self) -> dict[str, str]:
        return {r.id: r.name for r in registry.get("store").roommates()}

    def _describe(self, leg: Leg, names: dict[str, str]) -> str:
        dest = names[leg.to] if leg.to else leg.payee
        return f"{names[leg.from_]} to {dest} {money(leg.amount)}"

    def _run_leg(self, leg: Leg, title: str) -> str:
        amount = _valid_amount(leg.amount)
        nessie = registry.get("nessie")
        if leg.type in ("transfer", "scheduled_transfer"):
            if leg.to is None:
                raise ValueError(f"{leg.type} leg needs a `to` roommate")
            return nessie.transfer(leg.from_, leg.to, amount, title)
        if leg.payee is None:
            raise ValueError(f"{leg.type} leg needs a payee")
        if leg.type == "bill_payment":
            return nessie.pay_bill(leg.from_, leg.payee, amount, leg.date)
        return nessie.purchase(leg.from_, leg.payee, amount, title)

    def _run_due_legs(self, p: Proposal, today: str) -> tuple[list[Leg], str | None]:
        """Run p's due legs in order; stop at the first Nessie failure."""
        ran: list[Leg] = []
        for leg in p.legs:
            if leg.status != "pending" or leg.date > today:
                continue
            try:
                leg.nessie_id = self._run_leg(leg, p.title)
            except NessieError as e:
                leg.status = "failed"
                return ran, str(e)
            leg.status = "done"
            ran.append(leg.model_copy())
        return ran, None

    def _announce(self, text: str, amounts: set[float]) -> None:
        # Only leg amounts are allowed in group text — never balances/incomes.
        audit = registry.get("auditor").check(text, amounts, "group")
        if not audit.ok:
            text = "The treasurer finished a payment. Details are in the house view."
        registry.get("outbox").send(Reply(target=GroupTarget(), text=text))

    def _settle(self, p: Proposal, ran: list[Leg], error: str | None, verb: str) -> None:
        store = registry.get("store")
        names = self._names()
        if error:
            p.status = "failed"
            store.save_proposal(p)
            trace.log("treasurer", "failed", f"{p.id}: {error}")
            self._announce(f"A payment for {p.title} failed, so nothing else will go out. "
                           f"The house will follow up.", set())
            return
        store.save_proposal(p)
        for leg in ran:
            trace.log("treasurer", "executed", f"{p.id} {leg.type} {self._describe(leg, names)} "
                      f"(nessie {leg.nessie_id})")
        later = [leg for leg in p.legs if leg.status == "pending"]
        parts = [f"{verb}: " + "; ".join(self._describe(leg, names) for leg in ran)] if ran else []
        if later:
            parts.append("Scheduled: " + "; ".join(
                f"{self._describe(leg, names)} on {leg.date}" for leg in later))
        if parts:
            self._announce(". ".join(parts) + ".", {leg.amount for leg in p.legs})

    def execute(self, pid: str) -> list[Leg]:
        store = registry.get("store")
        p = store.get_proposal(pid)  # KeyError on unknown pid
        if p.status != "approved":
            raise ValueError(
                f"proposal {pid} is {p.status}; the treasurer only runs approved proposals")
        # Validate all due amounts before any Nessie write (fail closed).
        today = store.today()
        for leg in p.legs:
            if leg.status == "pending" and leg.date <= today:
                _valid_amount(leg.amount)
        ran, error = self._run_due_legs(p, today)
        if not error:
            p.status = "executed"
        self._settle(p, ran, error, f"Sent for {p.title}")
        return ran

    def run_due(self, today: str) -> list[Leg]:
        store = registry.get("store")
        ran_all: list[Leg] = []
        for p in store.proposals():
            # Only executed proposals with remaining pending legs; never retry failed.
            if p.status != "executed" or not any(
                    leg.status == "pending" and leg.date <= today for leg in p.legs):
                continue
            for leg in p.legs:
                if leg.status == "pending" and leg.date <= today:
                    _valid_amount(leg.amount)
            ran, error = self._run_due_legs(p, today)
            self._settle(p, ran, error, "Scheduled payment sent")
            ran_all += ran
        return ran_all
