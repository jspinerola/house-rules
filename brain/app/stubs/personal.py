"""Answers from expected.json and canned DMs."""
from __future__ import annotations

from contracts.models import Ask, DMTarget, Proposal, Release, Reply

from .. import fixtures, registry, trace


class StubPersonal:
    def ask(self, rid: str, question: Ask) -> Release:
        ans = registry.get("tools").can_cover(rid, question.amount, question.by_date)
        trace.log(f"personal:{rid}", "answered", ans.level)
        return Release(level=ans.level, earliest_date=ans.earliest_date)

    def dm(self, rid: str, text: str) -> list[Reply]:
        return [Reply(target=DMTarget(roommate_id=rid), text=fixtures.expected().scripts.dm_default)]

    def explain(self, rid: str, proposal: Proposal) -> list[Reply]:
        scripts = fixtures.expected().scripts
        if proposal.flow == "rent" and rid == "jordan":
            return [Reply(target=DMTarget(roommate_id=rid), text=scripts.rent_dm_jordan)]
        if proposal.flow == "rent" and rid == "alex":
            text = ("Rent is due. Jordan's payday is 2026-12-15, so the plan proposes you front "
                    "Jordan's $800 share now. Jordan auto-repays you on 2026-12-16. Reply yes to agree.")
            return [Reply(target=DMTarget(roommate_id=rid), text=text)]
        return []
