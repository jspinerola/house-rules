"""Proposal + approval state machine (PROPOSALS_MODE=real).

A reply applies to the roommate's oldest pending proposal. All required yeses -> approved
-> Treasurer.execute. Any no -> rejected. Every transition is traced.
"""
from __future__ import annotations

from contracts.models import Leg, Proposal, Verdict

from . import registry, trace, yesno


class Proposals:
    def parse(self, text: str) -> Verdict | None:
        return yesno.parse(text)

    def create(self, flow: str, title: str, legs: list[Leg], approvers: list[str]) -> Proposal:
        if not legs or not approvers:
            raise ValueError("a proposal needs at least one leg and one approver")
        store = registry.get("store")
        for rid in approvers:
            store.get_roommate(rid)  # raises on unknown roommate
        p = Proposal(id=f"p{len(store.proposals()) + 1}", flow=flow, title=title, legs=legs,
                     required_approvers=approvers, approvals={r: "pending" for r in approvers})
        store.save_proposal(p)
        total = round(sum(leg.amount for leg in legs), 2)
        trace.log("house", "proposed", f"{p.id} {title}: {len(legs)} legs, needs {', '.join(approvers)}"
                  f" (${total:,.2f} moved)")
        return p

    def record_reply(self, rid: str, text: str) -> Proposal | None:
        verdict = self.parse(text)
        if verdict is None:
            return None
        store = registry.get("store")
        pending = store.pending_for(rid)
        if not pending:
            return None
        p = pending[0]
        p.approvals[rid] = verdict
        trace.log(f"personal:{rid}", "approved" if verdict == "yes" else "declined", p.id)
        if verdict == "no":
            p.status = "rejected"
            store.save_proposal(p)
            trace.log("house", "rejected", f"{p.id} {p.title}: {rid} said no")
            return p
        if all(v == "yes" for v in p.approvals.values()):
            p.status = "approved"
            store.save_proposal(p)
            trace.log("house", "approved", f"{p.id} {p.title}: everyone said yes")
            registry.get("treasurer").execute(p.id)
            return store.get_proposal(p.id)
        store.save_proposal(p)
        return p

    def get(self, pid: str) -> Proposal:
        return registry.get("store").get_proposal(pid)

    def pending(self) -> list[Proposal]:
        return [p for p in registry.get("store").proposals() if p.status == "pending"]
