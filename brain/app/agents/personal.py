"""Personal agent (PERSONAL_MODE=real), one per roommate, living in that roommate's DM.

Sees only that roommate's accounts and indicators. Code decides every answer (Tools.can_cover);
the LLM only words the DM. With Grok, DMs run a tool loop (loop.py) over tools scoped to that
roommate; stub mode (or Grok down) uses the scripted keyword replies.
To the house agent it releases nothing but {level, earliest_date}.
"""
from __future__ import annotations

from collections import deque

from contracts.models import Ask, DMTarget, Proposal, Release, Reply

from .. import registry, trace
from ..fmt import money
from . import loop
from .loop import AgentTool, ToolOutput
from .voice import PERSONAS, RULES, speak

AGENT = """Answer this roommate's money questions with tools; quote their numbers exactly, never
estimate or do arithmetic, and always say the actual date (YYYY-MM-DD) when one matters.
my_money for balance, payday, runway and health indicators; can_i_cover for "can I afford X";
my_approvals for what's waiting on their yes; my_schedule for upcoming payments to or from them.
If nothing needs a tool, just reply. You can't move money; approvals happen when they reply yes."""


class PersonalAgent:
    def __init__(self) -> None:
        self._history: dict[str, deque[tuple[str, str]]] = {}  # per-DM recent chat

    def ask(self, rid: str, question: Ask) -> Release:
        ans = registry.get("tools").can_cover(rid, question.amount, question.by_date)
        release = Release(level=ans.level, earliest_date=ans.earliest_date)
        detail = f"{question.purpose}: {release.level}"
        if release.earliest_date:
            detail += f", can pay {release.earliest_date}"
        trace.log(f"personal:{rid}", "answered", detail)
        return release

    def _dm(self, rid: str, flow: str, draft: str, allowed: set[float],
            asked: str | None = None) -> list[Reply]:
        context = None
        if asked:
            name = next((r.name for r in registry.get("store").roommates() if r.id == rid), rid)
            context = f"{name}: {asked}"
        text = speak(f"personal:{rid}", flow, draft, allowed, rid, context)
        return [Reply(target=DMTarget(roommate_id=rid), text=text)]

    def dm(self, rid: str, text: str) -> list[Reply]:
        name = registry.get("store").get_roommate(rid).name
        hist = self._history.setdefault(rid, deque(maxlen=8))
        hist.append((name, text))
        context = "\n".join(f"{n}: {t}" for n, t in hist)
        agent = f"personal:{rid}"
        today = registry.get("store").today()
        out = loop.run(agent, f"{RULES}\n{PERSONAS['personal']}\nThis DM is with {name}. Today is {today}.\n{AGENT}",
                       f"CONVERSATION (most recent last):\n{context}\n\nAnswer {name}'s latest message.",
                       self._tools(rid))
        answer = None if loop.silent(out) else loop.checked(agent, out, rid, set())
        replies = ([Reply(target=DMTarget(roommate_id=rid), text=answer)] if answer is not None
                   else self._scripted_dm(rid, text))
        hist.extend(("You", r.text) for r in replies)
        return replies

    def _tools(self, rid: str) -> list[AgentTool]:
        store, tools = registry.get("store"), registry.get("tools")
        names = {r.id: r.name for r in store.roommates()}

        def my_money(args: dict) -> ToolOutput:
            ind = registry.get("indicators").compute(rid)
            indicators = {k: {"value": round(v.value * 100, 1) if k == "rent_to_income" else v.value,
                              "status": v.status} for k, v in ind.items()}
            indicators["rent_to_income"]["unit"] = "% of income"
            return ToolOutput({"today": store.today(), "checking_balance": registry.get("nessie").balance(rid),
                               "next_payday": tools.next_payday(rid, store.today()), "indicators": indicators})

        def can_i_cover(args: dict) -> ToolOutput:
            amount = args.get("amount")
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                raise ValueError("amount must be a number")
            by = str(args.get("by_date") or store.today())
            ans = tools.can_cover(rid, float(amount), by)
            return ToolOutput({"amount": amount, "by_date": by, "level": ans.level,
                               "earliest_date": ans.earliest_date,
                               "meaning": "ok = stays above $200 until payday, tight = above $0, no = goes negative"})

        def my_approvals(args: dict) -> ToolOutput:
            waiting = [{"title": p.title, "my_part": round(sum(l.amount for l in p.legs if l.from_ == rid), 2),
                        "waiting_on": [names[r] for r, v in p.approvals.items() if v == "pending"]}
                       for p in store.pending_for(rid)]
            return ToolOutput({"waiting_on_my_yes": waiting})

        def my_schedule(args: dict) -> ToolOutput:
            today, rows = store.today(), []
            for p in store.proposals():
                if p.status not in ("pending", "approved", "executed"):
                    continue
                for leg in p.legs:
                    if leg.status != "pending" or rid not in (leg.from_, leg.to):
                        continue
                    other = leg.to if leg.from_ == rid else leg.from_
                    rows.append({"date": leg.date, "amount": -leg.amount if leg.from_ == rid else leg.amount,
                                 "with": names.get(other or "", leg.payee), "for": p.title,
                                 "proposal_status": p.status})
            return ToolOutput({"today": today, "upcoming": sorted(rows, key=lambda r: r["date"])})

        return [
            AgentTool("my_money", "This roommate's checking balance, next payday and health indicators "
                      "(runway_days, days_to_payday, buffer_after rent, rent_to_income, ...).", {}, my_money),
            AgentTool("can_i_cover", "Can they cover an amount by a date? Returns ok/tight/no and, if no, "
                      "the earliest date they can.",
                      {"amount": {"type": "number"}, "by_date": {"type": "string", "description": "YYYY-MM-DD"}},
                      can_i_cover, ("amount",)),
            AgentTool("my_approvals", "Proposals waiting on their yes, with their part.", {}, my_approvals),
            AgentTool("my_schedule", "Upcoming payments to or from them (pending legs).", {}, my_schedule),
        ]

    def _scripted_dm(self, rid: str, text: str) -> list[Reply]:
        q = text.lower()
        if "runway" in q:
            ind = registry.get("indicators").compute(rid)
            runway = ind["runway_days"].value
            store = registry.get("store")
            payday = registry.get("tools").next_payday(rid, store.today())
            return self._dm(rid, "dm", f"At your usual spending your runway is about {runway:g} days, "
                            f"and your next payday is {payday}.", {runway}, text)
        if "balance" in q:
            bal = registry.get("nessie").balance(rid)
            return self._dm(rid, "dm", f"Your checking balance is {money(bal)}.", {bal}, text)
        waiting = registry.get("store").pending_for(rid)
        if waiting:
            return self._dm(rid, "dm", f"{waiting[0].title} is waiting on your yes. Reply yes or no.",
                            set(), text)
        return self._dm(rid, "small_talk", "I'm your personal agent. I only share ok, tight or no with the house. "
                        "Ask me about your runway or balance.", set(), text)

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
