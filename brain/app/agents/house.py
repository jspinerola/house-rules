"""House agent (HOUSE_MODE=real), living in the group chat.

Sees shared bills, house rules and whatever personal agents release (ok/tight/no or a date).
Tools: split_bill, group_affordability, payday_plan, ask_personal, create_proposal.
Every outgoing message goes through the Auditor (voice.speak).
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from contracts.models import Ask, DemoEvent, GroupTarget, Leg, Proposal, Release, Reply

from .. import registry, trace
from ..fmt import money
from .voice import speak

BILL_FLOWS = {"rent_due": ("rent", "rent"), "electric_bill": ("electric", "utility")}
BILL_EVENTS = {"rent": "rent_due", "electric": "electric_bill"}

# Grok picks the flow; code does every number (AGENTS.md: code does the math, the LLM explains).
ROUTER = """ROLE:ROUTER. You route roommate messages in the House Rules group chat to a tool.
- start_bill: someone says a shared bill (rent or electric) is due, coming up, or should be split/paid.
- group_affordability: someone asks whether the house can afford or split a purchase.
- small_talk: greetings, thanks, jokes, or anything that is not clearly about a bill or a purchase.
Only start a bill when the message is actually about that bill. Always call exactly one tool."""
ROUTER_TOOLS = [
    {"type": "function", "function": {
        "name": "start_bill",
        "description": "Start the bill flow: split it by house rules, ask each personal agent, propose payments.",
        "parameters": {"type": "object", "properties": {"bill": {"type": "string", "enum": ["rent", "electric"]}},
                       "required": ["bill"]}}},
    {"type": "function", "function": {
        "name": "group_affordability",
        "description": "Check whether everyone can cover a shared purchase and propose a plan.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "small_talk",
        "description": "Not about a bill or purchase: reply with a short intro.",
        "parameters": {"type": "object", "properties": {}}}},
]
PRICE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")
ITEM = re.compile(r"\$\s*[\d,]+(?:\.\d{1,2})?\s+([a-z][a-z ]*?)\s*(?:\?|$|for\b|from\b)")


def _group(text: str) -> Reply:
    return Reply(target=GroupTarget(), text=text)


def _shift_months(d: date, k: int) -> date:
    m = d.month - 1 + k
    return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


class HouseAgent:
    def _names(self) -> dict[str, str]:
        return {r.id: r.name for r in registry.get("store").roommates()}

    def _ask_personal(self, rid: str, amount: float, by: str, purpose: str) -> Release:
        trace.log("house", "asked", f"ask_personal {rid}: {purpose} {money(amount)} by {by}")
        return registry.get("personal").ask(rid, Ask(amount=amount, by_date=by, purpose=purpose))

    def _create(self, flow: str, title: str, legs: list[Leg], approvers: list[str]) -> Proposal:
        return registry.get("proposals").create(flow, title, legs, approvers)

    # ----- bills (rent day, utilities) -----

    def _bill_flow(self, bill_type: str, flow: str) -> list[Reply]:
        store, tools = registry.get("store"), registry.get("tools")
        names = self._names()
        bill = store.bill(bill_type)
        today = store.today()
        by = (date.fromisoformat(bill.due) - timedelta(days=1)).isoformat()
        shares = tools.split_bill(bill_type, bill.amount).shares
        releases = {rid: self._ask_personal(rid, amt, by, bill_type) for rid, amt in shares.items()}

        now: list[Leg] = []
        later: list[Leg] = []
        fronted: list[tuple[str, str, str]] = []  # (debtor, fronter, repay_date)
        for rid, amt in shares.items():
            if rid == bill.payer:
                continue
            if releases[rid].level != "no":
                now.append(Leg(type="transfer", **{"from": rid}, to=bill.payer, amount=amt, date=today))
                continue
            plan = tools.payday_plan(rid, amt)
            if plan.fronter != bill.payer:
                now.append(Leg(type="transfer", **{"from": plan.fronter}, to=bill.payer, amount=amt, date=today))
            later.append(Leg(type="scheduled_transfer", **{"from": rid}, to=plan.fronter, amount=amt,
                             date=plan.repay_date))
            fronted.append((rid, plan.fronter, plan.repay_date))
        pay = Leg(type="bill_payment", **{"from": bill.payer}, payee=bill.payee, amount=bill.amount, date=today)
        month = date.fromisoformat(bill.due).strftime("%B")
        title = f"{bill_type.capitalize()} for {month}"
        p = self._create(flow, title, now + [pay] + later, list(shares))

        amounts = set(shares.values())
        each = (f"{money(next(iter(amounts)))} each" if len(amounts) == 1 else
                ", ".join(f"{names[r]} {money(a)}" for r, a in shares.items()))
        senders = [names[r] for r in shares if r != bill.payer]
        draft = (f"{title.split(' for ')[0]} for {month} is {money(bill.amount)}, due {bill.due}: {each}. "
                 f"{_join(senders)} send their share to {names[bill.payer]}, then {names[bill.payer]} "
                 f"pays {bill.payee}.")
        for debtor, fronter, repay in fronted:
            draft += (f" {names[debtor]} can pay on {repay}, so {names[fronter]} fronts "
                      f"{names[debtor]}'s share until then.")
        draft += " Reply yes to approve."
        replies = [_group(speak("house", flow, draft, amounts | {bill.amount}, "group"))]
        personal = registry.get("personal")
        for debtor, fronter, _ in fronted:
            replies += personal.explain(debtor, p)
            replies += personal.explain(fronter, p)
        return replies

    # ----- group affordability -----

    def _afford(self, text: str) -> list[Reply]:
        store, tools = registry.get("store"), registry.get("tools")
        m = PRICE.search(text)
        if not m:
            return [_group(speak("house", "chat", "How much does it cost? Try \"can we afford a $1,200 couch?\"",
                                 {1200}, "group"))]
        price = float(m.group(1).replace(",", ""))
        im = ITEM.search(text.lower())
        item = im.group(1).strip() if im else "item"
        names = self._names()
        ids = list(names)
        today = store.today()
        upfront = round(price / len(ids), 2)

        aff = tools.group_affordability(item, price)
        if aff.plan is None:
            for rid in ids:
                self._ask_personal(rid, upfront, today, item)
            return [_group(speak("house", "couch", f"Even spread out, not everyone can swing a "
                                 f"{money(price)} {item} right now. Want to look at something cheaper?",
                                 {price}, "group"))]

        per, months = aff.plan.per_person_monthly, aff.plan.months
        releases = {rid: self._ask_personal(rid, per, today, item) for rid in ids}
        weakest = min(ids, key=lambda r: ["no", "tight", "ok"].index(releases[r].level))
        buyer = tools.payday_plan(weakest, price).fronter if releases[weakest].level != "ok" else ids[0]
        merchant = next((mm for mm in store_merchants() if item.split()[-1] in mm.lower()),
                        f"{item.title()} Store")

        start = date.fromisoformat(today)
        legs = [Leg(type="purchase", **{"from": buyer}, payee=merchant, amount=price, date=today)]
        last = round(upfront - per * (months - 1), 2)
        for k in range(months):
            for rid in ids:
                if rid != buyer:
                    legs.append(Leg(type="scheduled_transfer", **{"from": rid}, to=buyer,
                                    amount=last if k == months - 1 else per,
                                    date=_shift_months(start, k).isoformat()))
        self._create("purchase", f"{item.capitalize()} from {merchant}", legs, ids)

        levels = ", ".join(f"{names[r]} {releases[r].level}" for r in ids)
        payers = _join([names[r] for r in ids if r != buyer])
        if months == 1:
            draft = (f"Everyone can cover {money(per)} each up front: {levels}. {names[buyer]} buys the "
                     f"{money(price)} {item} from {merchant} and {payers} pay {names[buyer]} back now.")
        else:
            draft = (f"Up front ({money(upfront)} each) doesn't work for everyone. Over {months} months it's "
                     f"{money(per)}/mo each: {levels}. {names[buyer]} buys the {money(price)} {item} from "
                     f"{merchant} now and {payers} pay {names[buyer]} monthly.")
        draft += " Reply yes to approve."
        allowed = {price, upfront, per, last, float(months)}
        return [_group(speak("house", "couch", draft, allowed, "group"))]

    # ----- protocol -----

    def on_event(self, event: DemoEvent) -> list[Reply]:
        if event in BILL_FLOWS:
            bill_type, flow = BILL_FLOWS[event]
            return self._bill_flow(bill_type, flow)
        trace.log("watcher", "skipped", f"{event} is P1 (B8) and not built yet")
        return []

    def _route(self, text: str) -> tuple[str, dict]:
        """Ask the LLM which tool fits; fall back to keywords when it picks none (stub mode, Grok down)."""
        result = registry.get("llm").chat(
            [{"role": "system", "content": ROUTER}, {"role": "user", "content": text}], ROUTER_TOOLS)
        for call in result.tool_calls:
            if call.name == "start_bill" and call.args.get("bill") in BILL_EVENTS:
                return "start_bill", {"bill": call.args["bill"]}
            if call.name == "group_affordability":
                return "group_affordability", {}
            if call.name == "small_talk":
                return "", {}
        low = text.lower()
        if "afford" in low:
            return "group_affordability", {}
        for bill in BILL_EVENTS:
            if bill in low:
                return "start_bill", {"bill": bill}
        return "", {}

    def on_message(self, sender_rid: str, text: str) -> list[Reply]:
        tool, args = self._route(text)
        trace.log("house", "routed", f"{sender_rid}: {tool or 'chat'}")
        if tool == "group_affordability":
            return self._afford(text)
        if tool == "start_bill":
            bill_type, flow = BILL_FLOWS[BILL_EVENTS[args["bill"]]]
            if any(p.flow == flow and p.status == "pending" for p in registry.get("store").proposals()):
                return [_group(speak("house", "chat", f"The {bill_type} proposal is already out. "
                                     "Reply yes in your DM to approve it.", set(), "group"))]
            return self._bill_flow(bill_type, flow)
        return [_group(speak("house", "chat", "I'm the house agent. I split bills by your house rules, time "
                             "payments to paydays, and answer things like \"can we afford a $1,200 couch?\"",
                             {1200}, "group"))]


def store_merchants() -> list[str]:
    from .. import fixtures  # merchants are scenario data, not a store table in P0
    return fixtures.scenario().merchants
