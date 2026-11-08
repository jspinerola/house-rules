"""Approves on the first yes from any required approver; any no rejects."""
from __future__ import annotations

from contracts.models import HouseRule, Leg, Proposal, Verdict

from .. import house_rules, registry, trace, yesno


class StubProposals:
    def parse(self, text: str) -> Verdict | None:
        return yesno.parse(text)

    def create(self, flow: str, title: str, legs: list[Leg], approvers: list[str],
               rule: HouseRule | None = None) -> Proposal:
        store = registry.get("store")
        p = Proposal(id=f"p{len(store.proposals()) + 1}", flow=flow, title=title, legs=legs,
                     required_approvers=approvers, approvals={r: "pending" for r in approvers}, rule=rule)
        store.save_proposal(p)
        trace.log("house", "proposed", f"{p.id} {title}")
        return p

    def record_reply(self, rid: str, text: str) -> Proposal | None:
        verdict = self.parse(text)
        store = registry.get("store")
        pending = store.pending_for(rid)
        if verdict is None or not pending:
            return None
        p = pending[0]
        p.approvals[rid] = verdict
        p.status = "approved" if verdict == "yes" else "rejected"
        store.save_proposal(p)
        trace.log(f"personal:{rid}", "approved" if verdict == "yes" else "rejected", p.id)
        if p.status == "approved" and p.flow == "rule":
            return house_rules.apply(p)
        if p.status == "approved":
            registry.get("treasurer").execute(p.id)
        return store.get_proposal(p.id)

    def get(self, pid: str) -> Proposal:
        return registry.get("store").get_proposal(pid)

    def pending(self) -> list[Proposal]:
        return [p for p in registry.get("store").proposals() if p.status == "pending"]
