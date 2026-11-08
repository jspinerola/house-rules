"""Runs legs dated today or earlier through the Nessie registry entry; future legs stay pending."""
from __future__ import annotations

from contracts.models import GroupTarget, Leg, Reply

from .. import registry, trace


def run_leg(leg: Leg) -> str:
    nessie = registry.get("nessie")
    if leg.type in ("transfer", "scheduled_transfer"):
        return nessie.transfer(leg.from_, leg.to, leg.amount, "House Rules")
    if leg.type == "bill_payment":
        return nessie.pay_bill(leg.from_, leg.payee, leg.amount, leg.date)
    return nessie.purchase(leg.from_, leg.payee, leg.amount, "House Rules")


class StubTreasurer:
    def _run(self, pid: str, today: str) -> list[Leg]:
        store = registry.get("store")
        p = store.get_proposal(pid)
        ran = []
        for leg in p.legs:
            if leg.status == "pending" and leg.date <= today:
                leg.nessie_id = run_leg(leg)
                leg.status = "done"
                ran.append(leg)
        store.save_proposal(p)
        return ran

    def execute(self, pid: str) -> list[Leg]:
        store = registry.get("store")
        p = store.get_proposal(pid)
        if p.status != "approved":
            raise ValueError(f"proposal {pid} is {p.status}, not approved")
        ran = self._run(pid, store.today())
        p = store.get_proposal(pid)
        p.status = "executed"
        store.save_proposal(p)
        trace.log("treasurer", "executed", f"{pid}: {len(ran)} legs")
        registry.get("outbox").send(Reply(target=GroupTarget(), text=f"Done: {p.title} is executed."))
        return ran

    def run_due(self, today: str) -> list[Leg]:
        ran = []
        for p in registry.get("store").proposals():
            if p.status == "executed":
                ran += self._run(p.id, today)
        return ran
