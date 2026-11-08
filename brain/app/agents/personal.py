"""Personal agent (PERSONAL_MODE=real), one per roommate, living in that roommate's DM.

Sees only that roommate's accounts and indicators. Code decides every answer (Tools.can_cover);
the LLM only words the DM. With Grok, DMs run a tool loop (loop.py) over tools scoped to that
roommate; stub mode (or Grok down) uses the scripted keyword replies.
To the house agent it releases nothing but {level, earliest_date}.
"""
from __future__ import annotations

import re
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
my_approvals for what's waiting on their yes; my_schedule for upcoming payments to or from them;
my_profile for what you've learned about them (payroll vs side income, recurring charges, spending trend).
When they tell you how they want their money handled (a cushion to keep, a savings goal, a cap on
fronting for others, or anything about their situation), save it with set_preference and confirm it.
For "why am I tight / can I afford X" call can_i_cover (it gives the reason, recurring charges and
cushion) and my_profile, and explain with those specifics. Never count side income as certain.
A savings goal needs a monthly amount; if they didn't give one, ask instead of guessing.
You can't change house rules or how bills are split: that takes everyone's yes in the group chat.
If they ask, tell them to say it in the group (e.g. "rent should be 40/30/30 because ..."); never say a
rule is set. If nothing needs a tool, just reply. You can't move money; approvals happen when they reply yes."""
MAX_MONEY = 100_000.0
MAX_NOTES = 10
# "rent rule", "40/30/30", "split the electric": house rules, which only the group can set.
HOUSE_RULE_TALK = re.compile(r"\b(?:rule|split)\b|\b\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,3}\b", re.I)
REASONS = {"cushion": "the cushion they asked you to keep", "savings_goal": "their savings goal",
           "upcoming_bills": "recurring charges due before payday", "runway": "their runway is short"}


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
        prefs = registry.get("store").get_preferences(rid)
        known = f"\nWhat {name} has told you: {'; '.join(prefs.notes)}" if prefs.notes else ""
        system = f"{RULES}\n{PERSONAS['personal']}\nThis DM is with {name}. Today is {today}.{known}\n{AGENT}"
        out = loop.run(agent, system,
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
            prof = registry.get("indicators").profile(rid)
            prefs = prof.preferences
            return ToolOutput({"amount": amount, "by_date": by, "level": ans.level,
                               "earliest_date": ans.earliest_date,
                               "reason": REASONS.get(ans.reason or "", None),
                               "recurring_charges": [r.model_dump() for r in prof.recurring],
                               "next_payday": tools.next_payday(rid, store.today()),
                               "cushion": max(200.0, prefs.min_buffer or 0.0),
                               "savings_monthly": prefs.savings_monthly,
                               "side_income_not_counted": prof.side_income_monthly or None,
                               "meaning": "ok = stays above the cushion until payday, tight = above $0, "
                                          "no = goes negative"})

        def my_profile(args: dict) -> ToolOutput:
            prof = registry.get("indicators").profile(rid)
            return ToolOutput(prof.model_dump(exclude={"indicators"}))

        def money_arg(value: object, what: str) -> float:
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= MAX_MONEY:
                raise ValueError(f"{what} must be a dollar amount from 0 to {MAX_MONEY:,.0f}")
            return round(float(value), 2)

        def set_preference(args: dict) -> ToolOutput:
            kind, value = str(args.get("kind", "")), args.get("value")
            prefs = store.get_preferences(rid)
            if kind == "min_buffer":
                prefs.min_buffer = money_arg(value, "the cushion")
            elif kind == "savings_goal":
                prefs.savings_monthly = money_arg(value, "the monthly savings amount")
                prefs.savings_label = str(args.get("label") or "savings")[:60]
            elif kind == "front_cap":
                prefs.front_cap = money_arg(value, "the fronting cap")
            elif kind == "add_note":
                note = str(value or "").strip()[:200]
                if not note:
                    raise ValueError("the note is empty")
                if HOUSE_RULE_TALK.search(note):
                    raise ValueError("that's a house rule, not a personal note: house rules need everyone's yes. "
                                     "Tell them to say it in the group chat, e.g. 'rent should be 40/30/30 "
                                     "because ...'. Nothing was saved.")
                if note not in prefs.notes:
                    prefs.notes = (prefs.notes + [note])[-MAX_NOTES:]
            elif kind == "remove_note":
                needle = str(value or "").lower()
                prefs.notes = [n for n in prefs.notes if needle not in n.lower()]
            elif kind == "clear":
                target = str(value or "")
                fields = {"min_buffer": ("min_buffer",), "savings_goal": ("savings_monthly", "savings_label"),
                          "front_cap": ("front_cap",), "notes": ()}
                if target not in fields:
                    raise ValueError(f"clear one of {sorted(fields)}")
                for f in fields[target]:
                    setattr(prefs, f, None)
                if target == "notes":
                    prefs.notes = []
            else:
                raise ValueError("kind must be min_buffer, savings_goal, front_cap, add_note, remove_note or clear")
            store.save_preferences(rid, prefs)
            trace.log(f"personal:{rid}", "preference_set", kind)  # never the value: the dashboard is public
            return ToolOutput({"saved": kind, "preferences": prefs.model_dump()})

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
            AgentTool("my_profile", "What you've learned from their bank history: income pattern (payroll vs "
                      "side income), recurring charges with next dates, spending trend, and their preferences.",
                      {}, my_profile),
            AgentTool("set_preference", "Save how they want their money handled. kind: min_buffer (keep at "
                      "least this in checking), savings_goal (monthly amount + label), front_cap (max to front "
                      "for a roommate), add_note / remove_note (their situation, in their words), clear "
                      "(value = which one to clear). Takes effect right away.",
                      {"kind": {"type": "string", "enum": ["min_buffer", "savings_goal", "front_cap",
                                                            "add_note", "remove_note", "clear"]},
                       "value": {"description": "Dollar amount, note text, or what to clear."},
                       "label": {"type": "string", "description": "Savings goal name, e.g. Japan trip."}},
                      set_preference, ("kind",)),
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

    def _why_short(self, rid: str, share: float, payday: str) -> tuple[str, set[float]]:
        """Why this roommate can't cover `share` before payday, in their own numbers (DM only)."""
        store = registry.get("store")
        balance = round(registry.get("nessie").balance(rid), 2)
        renewing = [r for r in registry.get("indicators").profile(rid).recurring
                    if store.today() < r.next_date <= payday]
        renew = round(sum(r.amount for r in renewing), 2)
        left = round(balance - share, 2)
        after = round(left - renew, 2)
        numbers = {balance, share, abs(left), renew, abs(after)} | {r.amount for r in renewing}
        if left < 0:
            return (f"Your {money(balance)} doesn't cover the {money(share)} share before your {payday} payday",
                    numbers)
        if renewing:
            what = " and ".join(r.name for r in renewing)
            end = (f"so you'd be {money(-after)} short" if after < 0
                   else f"leaving only {money(after)}")
            return (f"After your {money(share)} share you'd have {money(left)}, and {what} ({money(renew)}) "
                    f"renew before your {payday} payday, {end}", numbers)
        return f"After your {money(share)} share you'd have only {money(left)} until your {payday} payday", numbers

    def explain(self, rid: str, proposal: Proposal) -> list[Reply]:
        store, tools = registry.get("store"), registry.get("tools")
        names = {r.id: r.name for r in store.roommates()}
        repay = next((leg for leg in proposal.legs
                      if leg.from_ == rid and leg.type == "scheduled_transfer" and leg.to), None)
        if proposal.flow == "rent" and repay is not None:
            share = tools.split_bill("rent", store.bill("rent").amount).shares[rid]
            payday = tools.next_payday(rid, store.today())
            fronter = names[repay.to]
            why, numbers = self._why_short(rid, share, payday or repay.date)
            draft = (f"{why}. So {fronter} fronts your share now and you auto-repay {fronter} "
                     f"{money(repay.amount)} on {repay.date}. Reply yes to agree.")
            return self._dm(rid, "front", draft, {share, repay.amount} | numbers)
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
