"""Personal agent (PERSONAL_MODE=real), one per roommate, living in that roommate's DM.

Sees only that roommate's accounts and indicators. Code decides every answer (Tools.can_cover);
the LLM only words the DM. To the house agent it releases nothing but {level, earliest_date}.
"""
from __future__ import annotations

from contracts.models import Ask, DMTarget, Proposal, Release, Reply

from .. import registry, trace
from ..fmt import money
from .voice import speak


class PersonalAgent:
    def ask(self, rid: str, question: Ask) -> Release:
        ans = registry.get("tools").can_cover(rid, question.amount, question.by_date)
        release = Release(level=ans.level, earliest_date=ans.earliest_date)
        detail = f"{question.purpose}: {release.level}"
        if release.earliest_date:
            detail += f", can pay {release.earliest_date}"
        trace.log(f"personal:{rid}", "answered", detail)
        return release

    def _dm(self, rid: str, flow: str, draft: str, allowed: set[float]) -> list[Reply]:
        text = speak(f"personal:{rid}", flow, draft, allowed, rid)
        return [Reply(target=DMTarget(roommate_id=rid), text=text)]

    def dm(self, rid: str, text: str) -> list[Reply]:
        q = text.lower()
        if "runway" in q:
            ind = registry.get("indicators").compute(rid)
            runway = ind["runway_days"].value
            store = registry.get("store")
            payday = registry.get("tools").next_payday(rid, store.today())
            return self._dm(rid, "dm", f"At your usual spending your runway is about {runway:g} days, "
                            f"and your next payday is {payday}.", {runway})
        if "balance" in q:
            bal = registry.get("nessie").balance(rid)
            return self._dm(rid, "dm", f"Your checking balance is {money(bal)}.", {bal})
        waiting = registry.get("store").pending_for(rid)
        if waiting:
            return self._dm(rid, "dm", f"{waiting[0].title} is waiting on your yes. Reply yes or no.", set())
        return self._dm(rid, "dm", "I'm your personal agent. I only share ok, tight or no with the house. "
                        "Ask me about your runway or balance.", set())

    def explain(self, rid: str, proposal: Proposal) -> list[Reply]:
        store, tools = registry.get("store"), registry.get("tools")
        names = {r.id: r.name for r in store.roommates()}
        repay = next((leg for leg in proposal.legs
                      if leg.from_ == rid and leg.type == "scheduled_transfer" and leg.to), None)
        if proposal.flow == "rent" and repay is not None:
            share = tools.split_bill("rent", store.bill("rent").amount).shares[rid]
            payday = tools.next_payday(rid, store.today())
            fronter = names[repay.to]
            draft = (f"Rent is {money(share)} and your payday is {payday}, so {fronter} fronts your share "
                     f"now and you auto-repay {fronter} {money(repay.amount)} on {repay.date}. "
                     f"Reply yes to agree.")
            return self._dm(rid, "front", draft, {share, repay.amount})
        fronting = next((leg for leg in proposal.legs
                         if leg.to == rid and leg.type == "scheduled_transfer"), None)
        if proposal.flow == "rent" and fronting is not None:
            debtor = names[fronting.from_]
            payday = tools.next_payday(fronting.from_, store.today())
            draft = (f"Rent is due. {debtor}'s payday is {payday}, so the plan proposes you front "
                     f"{debtor}'s {money(fronting.amount)} share now. {debtor} auto-repays you on "
                     f"{fronting.date}. Reply yes to agree.")
            return self._dm(rid, "front", draft, {fronting.amount})
        mine = [leg for leg in proposal.legs if leg.from_ == rid]
        if not mine:
            return []
        total = round(sum(leg.amount for leg in mine), 2)
        return self._dm(rid, "dm", f"{proposal.title}: your part is {money(total)} in total. "
                        f"Reply yes to agree.", {total})
