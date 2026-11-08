"""House agent (HOUSE_MODE=real), living in the group chat.

Sees shared bills, house rules and whatever personal agents release (ok/tight/no or a date).
With Grok, the agent runs a tool loop (loop.py): it reads house status, splits, what-ifs and
personal ok/tight/no answers, then answers or starts an action (bill flow, purchase proposal).
Code does every number; every outgoing message goes through the Auditor.
Stub mode (or Grok down) falls back to keyword routing into the same scripted flows.
"""
from __future__ import annotations

import re
from collections import deque
from datetime import date, timedelta

from contracts.models import Ask, DemoEvent, GroupTarget, HouseRule, Leg, Proposal, Release, Reply

from .. import fixtures, registry, trace
from ..fmt import money
from . import loop
from .auditor import numbers_in
from .loop import AgentTool, ToolOutput
from .voice import PERSONAS, RULES, speak

BILL_FLOWS = {"rent_due": ("rent", "rent"), "electric_bill": ("electric", "utility")}
BILL_EVENTS = {"rent": "rent_due", "electric": "electric_bill"}
BILL_FLOW = {bill: flow for bill, flow in BILL_FLOWS.values()}  # "rent" -> "rent", "electric" -> "utility"
BILL_FLOW["purchase"] = "purchase"  # the default split for shared buys (house rule, no bill behind it)
RULE_BILLS = sorted(BILL_FLOW)
RULE_EXAMPLE = 100.0  # preview amount for a purchase rule when nobody named a price

# The LLM picks tools and explains; code does every number (AGENTS.md).
AGENT = """You run the house's money in this group chat. Use tools for every fact or number; never
do arithmetic yourself (no rounding, no totals), quote tool numbers exactly:
- house_status for bills, due dates, house rules, pending proposals, who owes whom.
- split_bill / what_if_purchase / can_cover to look things up without committing to anything.
- propose_rule when roommates agree on how a bill should be split and why ("Alex has the master,
  rent 40/30/30"; bill "purchase" = the default split for shared buys); remove_rule to go back to
  an even split. Both post a vote, so call and stop.
- For one purchase split unevenly ("Alex pays half since it's in Alex's room"), pass shares and
  reason to group_affordability / what_if_purchase instead of making a house rule.
- start_bill or group_affordability ONLY when the roommates want to actually set up a bill payment
  or purchase; those post the proposal themselves, so call them and stop.
Never say you'll check or set something up: call the tool in this same turn.
"can we afford X" -> group_affordability; "what if / how about over N months" -> what_if_purchase;
"let's do rent" / "rent is due" -> start_bill. Only say "reply yes" right after an ACTION posted it.
Pass a price only if a roommate stated it. If nothing needs a tool (greetings, jokes, thanks), just reply.
Never end with a yes/no question: "yes" approves whatever proposal is open. Proposing only opens a
vote, so when someone states a lasting split ("Alex should pay 50% of all shared furniture") call
propose_rule right away; for anything else say "say the word and I'll put it to a vote".
You cannot record approvals. Only a reply of yes / y / yep / ok / approve counts; if someone agrees in
other words ("lets do that"), tell them to reply yes. Never say someone approved unless a tool says so. Never mention balances or incomes; personal agents only tell you ok, tight, no or a date."""
INTRO = ("I'm the house agent. I split bills by your house rules, time payments to paydays, and answer "
         "things like \"can we afford a $1,200 couch?\"")
# "$1,200", "1200", "1.2k"; the amount right after it is the item ("1200 couch").
AMOUNT = re.compile(r"(?<![\w.])(\$)?\s*(\d[\d,]*(?:\.\d{1,2})?)(\s*k\b)?")
NOT_PRICE = re.compile(r"\s*(?:months?|mos?\b|weeks?|days?|years?|%|x\b|ways?|people|of us)")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b")
ITEM_AFTER = re.compile(r"\s*(?:dollars?\s+|bucks\s+)?([a-z]+(?:\s+[a-z]+)?)")
ITEM_BEFORE = re.compile(r"\b(?:a|an|the|some)\s+(?:(?:new|nice|big|used|cheap)\s+)?([a-z]+)")
BARE_PRICE = re.compile(r"^\s*(?:it'?s\s+|about\s+|like\s+)?\$?\s*\d[\d,]*(?:\.\d{1,2})?\s*k?"
                        r"\s*(?:bucks|dollars)?\s*[.!?]*\s*$", re.I)
NOT_ITEMS = {"lot", "bit", "few", "month", "months", "plan", "dollar", "dollars", "bucks", "new"}
# Words that end an item name: "1200 couch doable for us", "1200 tv 3 ways".
ITEM_STOP = {"doable", "possible", "for", "from", "over", "in", "split", "is", "are", "and", "or", "if",
             "with", "now", "today", "this", "that", "ok", "okay", "work", "worth", "each", "total",
             "together", "up", "monthly", "a", "the", "to", "between", "across", "at", "on", "by"}


def parse_purchase(text: str) -> tuple[float | None, str | None]:
    """Price and item typed by a roommate; a `$` amount wins, month counts and dates are skipped."""
    low = DATE.sub(" ", text.lower())
    found: list[tuple[bool, float, str]] = []
    for m in AMOUNT.finditer(low):
        rest = low[m.end():]
        if NOT_PRICE.match(rest) and not m.group(1):
            continue
        value = float(m.group(2).replace(",", "")) * (1000 if m.group(3) else 1)
        im = ITEM_AFTER.match(rest)
        words = im.group(1).split() if im else []
        item = []
        for w in words:
            if w in ITEM_STOP:
                break
            item.append(w)
        found.append((bool(m.group(1)), value, " ".join(item)))
    if not found:
        return None, _item_before(low)
    _, price, item = max(found, key=lambda f: f[0])
    item = " ".join(w for w in item.split() if w not in NOT_ITEMS)
    return price, item or _item_before(low)


def _item_before(low: str) -> str | None:
    for m in ITEM_BEFORE.finditer(low.replace("afford", " ")):
        if m.group(1) not in NOT_ITEMS:
            return m.group(1)
    return None


def _typed(price: float, text: str) -> bool:
    """True when `price` is a number the roommate actually typed (1.2k counts as 1200)."""
    return any(abs(price - n) < 0.005 or abs(price - n * 1000) < 0.5 for n in numbers_in(text))


def _group(text: str) -> Reply:
    return Reply(target=GroupTarget(), text=text)


def _shift_months(d: date, k: int) -> date:
    m = d.month - 1 + k
    return date(d.year + m // 12, m % 12 + 1, min(d.day, 28))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


class HouseAgent:
    def __init__(self) -> None:
        # Recent group chat (name, text) so Grok can follow the thread; reset with the registry.
        self._history: deque[tuple[str, str]] = deque(maxlen=10)
        self._pending_item: str | None = None  # asked "what's the price?" for this item

    def _context(self) -> str:
        return "\n".join(f"{n}: {t}" for n, t in self._history)

    def _say(self, flow: str, draft: str, allowed: set[float]) -> Reply:
        return _group(speak("house", flow, draft, allowed, "group", self._context()))

    def _names(self) -> dict[str, str]:
        return {r.id: r.name for r in registry.get("store").roommates()}

    def _ask_personal(self, rid: str, amount: float, by: str, purpose: str) -> Release:
        trace.log("house", "asked", f"ask_personal {rid}: {purpose} {money(amount)} by {by}")
        return registry.get("personal").ask(rid, Ask(amount=amount, by_date=by, purpose=purpose))

    def _create(self, flow: str, title: str, legs: list[Leg], approvers: list[str],
                rule: HouseRule | None = None) -> Proposal:
        return registry.get("proposals").create(flow, title, legs, approvers, rule=rule)

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
            try:
                plan = tools.payday_plan(rid, amt)
            except ValueError:  # every possible fronter capped their fronting below this share
                trace.log("house", "no_fronter", f"{rid} {money(amt)} {bill_type}")
                draft = (f"{names[rid]} can't cover their {money(amt)} {bill_type} share until "
                         f"{releases[rid].earliest_date or 'their next payday'}, and nobody is set up to "
                         f"front it right now. Want to hold the {bill_type} until then?")
                return [self._say(flow, draft, {amt})]
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
        replies = [self._say(flow, draft, amounts | {bill.amount})]
        personal = registry.get("personal")
        for debtor, fronter, _ in fronted:
            replies += personal.explain(debtor, p)
            replies += personal.explain(fronter, p)
        return replies

    # ----- group affordability -----

    def _afford(self, text: str, price: float | None = None, item: str | None = None,
                months: int | None = None, typed_in: str | None = None,
                shares: dict[str, float] | None = None, reason: str | None = None) -> list[Reply]:
        """Shared purchase: `shares` is a one-off split (fractions); else the purchase rule; else even."""
        store, tools = registry.get("store"), registry.get("tools")
        parsed_price, parsed_item = parse_purchase(text)
        if price is None or not _typed(price, typed_in or text):
            price = parsed_price  # never trust a price the roommate didn't type
        if not item or not re.fullmatch(r"[a-zA-Z][a-zA-Z ]{0,30}", item):
            item = parsed_item
        item = (item or self._pending_item or "item").strip().lower()
        if not price:
            self._pending_item = item
            thing = "it" if item == "item" else f"the {item}"
            return [self._say("chat", f"Happy to check. How much is {thing}?", set())]
        self._pending_item = None
        names = self._names()
        ids = list(names)
        today = store.today()
        one_off = (HouseRule(id="one-off", bill_type="purchase", split=shares, source_text=reason or "one-off")
                   if shares is not None else None)
        rule = one_off or store.house_rule("purchase")
        owed = tools.split_bill("purchase", price, rule=one_off).shares
        why = f" ({rule.source_text})" if rule and rule.split else ""

        aff = tools.group_affordability(item, price, (months,) if months else (1, 3), shares=shares)
        if aff.plan is None:
            for rid in ids:
                self._ask_personal(rid, owed[rid], today, item)
            return [self._say("couch", f"Even spread out, not everyone can swing a {money(price)} {item} "
                              "right now. Want to look at something cheaper?", {price})]

        months = aff.plan.months
        monthly = aff.plan.monthly or {rid: aff.plan.per_person_monthly for rid in ids}
        last = {rid: round(owed[rid] - monthly[rid] * (months - 1), 2) for rid in ids}
        releases = {rid: self._ask_personal(rid, monthly[rid], today, item) for rid in ids}
        weakest = min(ids, key=lambda r: ["no", "tight", "ok"].index(releases[r].level))
        buyer = tools.payday_plan(weakest, price).fronter if releases[weakest].level != "ok" else ids[0]
        merchant = next((mm for mm in store_merchants() if item.split()[-1] in mm.lower()),
                        f"{item.title()} Store")

        start = date.fromisoformat(today)
        legs = [Leg(type="purchase", **{"from": buyer}, payee=merchant, amount=price, date=today)]
        for k in range(months):
            for rid in ids:
                if rid != buyer:
                    legs.append(Leg(type="scheduled_transfer", **{"from": rid}, to=buyer,
                                    amount=last[rid] if k == months - 1 else monthly[rid],
                                    date=_shift_months(start, k).isoformat()))
        self._create("purchase", f"{item.capitalize()} from {merchant}", legs, ids)

        levels = ", ".join(f"{names[r]} {releases[r].level}" for r in ids)
        payers = _join([names[r] for r in ids if r != buyer])
        uneven = bool(aff.plan.monthly)
        each = (lambda amounts, unit: ", ".join(f"{names[r]} {money(amounts[r])}{unit}" for r in ids)
                if uneven else f"{money(amounts[ids[0]])}{unit} each")
        if months == 1 and not uneven:
            draft = (f"Everyone can cover {each(monthly, '')} up front: {levels}. {names[buyer]} buys the "
                     f"{money(price)} {item} from {merchant} and {payers} pay {names[buyer]} back now.")
        elif months == 1:
            draft = (f"Everyone can cover their part up front{why}: {each(monthly, '')}; {levels}. "
                     f"{names[buyer]} buys the {money(price)} {item} from {merchant} and {payers} pay "
                     f"{names[buyer]} back now.")
        else:
            draft = (f"Up front ({each(owed, '')}) doesn't work for everyone. Over {months} months{why} it's "
                     f"{each(monthly, '/mo')}: {levels}. {names[buyer]} buys the {money(price)} {item} from "
                     f"{merchant} now and {payers} pay {names[buyer]} monthly.")
        draft += " Reply yes to approve."
        allowed = {price, float(months)} | set(owed.values()) | set(monthly.values()) | set(last.values())
        if rule and rule.split:
            allowed |= {round(f * 100, 2) for f in rule.split.values()}
        return [self._say("couch", draft, allowed)]

    # ----- protocol -----

    def on_event(self, event: DemoEvent) -> list[Reply]:
        if event in BILL_FLOWS:
            bill_type, flow = BILL_FLOWS[event]
            return self._remember(self._bill_flow(bill_type, flow))
        trace.log("watcher", "skipped", f"{event} is P1 (B8) and not built yet")
        return []

    def _remember(self, replies: list[Reply]) -> list[Reply]:
        self._history.extend(("House", r.text) for r in replies if r.target.type == "group")
        return replies

    def on_message(self, sender_rid: str, text: str) -> list[Reply]:
        name = self._names().get(sender_rid, sender_rid)
        self._history.append((name, text))
        if self._pending_item and BARE_PRICE.match(text):  # answering "how much is it?"
            trace.log("house", "routed", f"{sender_rid}: group_affordability")
            return self._remember(self._afford(text))
        return self._remember(self._agent_turn(sender_rid, name, text))

    def _agent_turn(self, sender_rid: str, name: str, text: str) -> list[Reply]:
        user = f"CONVERSATION (most recent last):\n{self._context()}\n\nAnswer {name}'s latest message."
        system = f"{RULES}\n{PERSONAS['house']}\n{AGENT}\nToday is {registry.get('store').today()}."
        out = loop.run("house", system, user, self._tools(text))
        trace.log("house", "routed", f"{sender_rid}: {', '.join(out.tools_used) or 'chat'}")
        if out.replies is not None:
            return out.replies
        if loop.silent(out):  # stub mode or Grok down: keyword routing keeps the demo alive
            return self._keyword_turn(text)
        answer = loop.checked("house", out, "group", set(numbers_in(self._context())))
        if answer is None:
            return self._small_talk()
        return [_group(answer)]

    def _keyword_turn(self, text: str) -> list[Reply]:
        low = text.lower()
        if "afford" in low:
            return self._afford(text)
        for bill in BILL_EVENTS:
            if bill in low:
                return self._start_bill(bill)
        return self._small_talk()

    def _small_talk(self) -> list[Reply]:
        self._pending_item = None
        return [self._say("small_talk", INTRO, {1200})]

    def _start_bill(self, bill: str) -> list[Reply]:
        self._pending_item = None
        bill_type, flow = BILL_FLOWS[BILL_EVENTS[bill]]
        if any(p.flow == flow and p.status == "pending" for p in registry.get("store").proposals()):
            return [self._say("chat", f"The {bill_type} proposal is already out. "
                              "Reply yes in your DM to approve it.", set())]
        return self._bill_flow(bill_type, flow)

    # ----- tools the LLM may call -----

    def _tools(self, text: str) -> list[AgentTool]:
        store, tools = registry.get("store"), registry.get("tools")
        names = self._names()
        ids = {n.lower(): rid for rid, n in names.items()} | {rid: rid for rid in names}

        def rid_of(who: object) -> str:
            rid = ids.get(str(who).strip().lower())
            if rid is None:
                raise ValueError(f"unknown roommate {who!r}; use one of {sorted(names.values())}")
            return rid

        def bill_of(args: dict) -> str:
            bill = str(args.get("bill", "")).lower()
            if bill not in BILL_EVENTS:
                raise ValueError(f"unknown bill {bill!r}; use one of {sorted(BILL_EVENTS)}")
            return bill

        def rule_bill_of(args: dict) -> str:
            bill = str(args.get("bill", "")).lower()
            if bill not in BILL_FLOW:
                raise ValueError(f"unknown bill {bill!r}; use one of {RULE_BILLS}")
            return bill

        def price_of(args: dict) -> float:
            price = args.get("price")
            if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
                raise ValueError("price must be a positive number")
            if not _typed(float(price), self._context()):
                raise ValueError("nobody stated that price; ask the roommates how much it costs")
            return float(price)

        def months_of(args: dict) -> int | None:
            m = args.get("months")
            if m is None:
                return None
            if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 12:
                raise ValueError("months must be a whole number from 1 to 12")
            return m

        def house_status(args: dict) -> ToolOutput:
            today = store.today()
            bills = []
            for bill in BILL_EVENTS:
                b = store.bill(bill)
                rule = store.house_rule(bill)
                shares = tools.split_bill(bill, b.amount).shares
                bills.append({"bill": bill, "amount": b.amount, "due": b.due, "payer": names[b.payer],
                              "shares": {names[r]: a for r, a in shares.items()},
                              "payee": b.payee,
                              "house_rule": ({"split": {names[r]: f"{f:.0%}" for r, f in rule.split.items()},
                                              "reason": rule.source_text, "rest": "split evenly"}
                                             if rule else "split evenly")})
            proposals = [{"title": pr.title, "status": pr.status,
                          "approved": [names[r] for r, v in pr.approvals.items() if v == "yes"],
                          "waiting_on": [names[r] for r, v in pr.approvals.items() if v == "pending"]}
                         for pr in store.proposals()]
            owes = [{"from": names[leg.from_], "to": names[leg.to], "amount": leg.amount, "due": leg.date}
                    for pr in store.proposals() if pr.status in ("approved", "executed")
                    for leg in pr.legs if leg.status == "pending" and leg.to in names]
            buy = store.house_rule("purchase")
            purchase_rule = ({"split": {names[r]: f"{f:.0%}" for r, f in buy.split.items()},
                              "reason": buy.source_text, "rest": "split evenly"} if buy else "split evenly")
            return ToolOutput({"today": today, "roommates": list(names.values()), "bills": bills,
                               "shared_purchases": purchase_rule, "proposals": proposals, "owes": owes})

        def split_bill(args: dict) -> ToolOutput:
            bill = bill_of(args)
            amount = args.get("amount", store.bill(bill).amount)
            shares = tools.split_bill(bill, amount).shares
            return ToolOutput({"bill": bill, "total": amount, "shares": {names[r]: a for r, a in shares.items()}})

        def what_if_purchase(args: dict) -> ToolOutput:
            price, months = price_of(args), months_of(args) or 1
            item = str(args.get("item") or "item")
            one_off = shares_of(args) if args.get("shares") else None
            rule = (HouseRule(id="one-off", bill_type="purchase", split=one_off, source_text="one-off")
                    if one_off is not None else None)
            owed = tools.split_bill("purchase", price, rule=rule).shares
            today = store.today()
            options = [months] if args.get("months") is not None else [1, 3]
            plans = []
            for m in options:  # same order as group_affordability: up front first, then spread out
                per = {r: round(a / m, 2) for r, a in owed.items()}
                plans.append({"months": m, "works_for_everyone": True, "per_person": [
                    {"name": names[r], "pays_total": owed[r], "pays_per_month": per[r],
                     "answer": self._ask_personal(r, per[r], today, item).level} for r in names]})
                plans[-1]["works_for_everyone"] = all(x["answer"] != "no" for x in plans[-1]["per_person"])
            return ToolOutput({"item": item, "price": price,
                               "split": "one-off" if one_off is not None else
                                        ("purchase house rule" if store.house_rule("purchase") else "even"),
                               "plans": plans,
                               "note": "what-if only: nothing proposed. Quote each person's own numbers "
                                       "from per_person; don't tell anyone to reply yes."})

        def can_cover(args: dict) -> ToolOutput:
            rid = rid_of(args.get("roommate"))
            amount = args.get("amount")
            if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                raise ValueError("amount must be a number")
            by = str(args.get("by_date") or store.today())
            rel = self._ask_personal(rid, float(amount), by, str(args.get("purpose") or "question"))
            return ToolOutput({"roommate": names[rid], "level": rel.level, "earliest_date": rel.earliest_date})

        def shares_of(args: dict) -> dict[str, float]:
            raw = args.get("shares")
            if not isinstance(raw, dict) or not raw:
                raise ValueError("shares must map roommate names to percents, e.g. {\"Alex\": 40}")
            split: dict[str, float] = {}
            for who, pct in raw.items():
                if not isinstance(pct, (int, float)) or isinstance(pct, bool) or not 0 <= pct <= 100:
                    raise ValueError(f"{who}'s share must be a percent from 0 to 100")
                split[rid_of(who)] = round(float(pct) / 100, 4)
            total = sum(split.values())
            if total > 1.0001:
                raise ValueError(f"shares add up to {total * 100:g}%, more than 100%")
            if len(split) == len(names) and abs(total - 1) > 0.0001:
                raise ValueError(f"everyone is listed, so shares must add up to 100%, not {total * 100:g}%")
            if len(split) == len(names):  # keep one roommate implicit so rounding cents land somewhere
                split.pop(min(split, key=split.get))
            return split

        def vote_open(bill: str) -> None:
            if any(pr.flow == "rule" and pr.status == "pending" and pr.rule and pr.rule.bill_type == bill
                   for pr in store.proposals()):
                raise ValueError(f"there's already a {bill} rule vote open; wait for it to finish")

        def rule_vote(bill: str, rule: HouseRule, title: str, lead: str) -> ToolOutput:
            if bill == "purchase":  # no bill behind it: preview on the price they named, else an example
                named = parse_purchase(text)[0]
                amount = named if named and _typed(named, self._context()) else RULE_EXAMPLE
                what = f"a {money(amount)} shared purchase"
            else:
                amount, what = store.bill(bill).amount, bill
            preview = tools.split_bill(bill, amount, rule=rule).shares
            p = self._create("rule", title, [], list(names), rule)
            split = ", ".join(f"{names[r]} {money(a)}" for r, a in preview.items())
            draft = f"{lead} {what} would be {split}. Everyone reply yes to make it the house rule."
            flow = BILL_FLOW[bill]
            if any(pr.flow == flow and pr.status == "pending" for pr in store.proposals()):
                draft += f" The {bill} proposal already out keeps its current split."
            allowed = set(preview.values()) | {amount} | {round(f * 100, 2) for f in rule.split.values()}
            return ToolOutput({"proposal": p.id}, [self._say("rule", draft, allowed)])

        def propose_rule(args: dict) -> ToolOutput:
            bill = rule_bill_of(args)
            vote_open(bill)
            split = shares_of(args)
            reason = str(args.get("reason") or "").strip()[:120] or "the house agreed"
            current = store.house_rule(bill)
            if current and current.split == split:
                raise ValueError(f"that is already the {bill} rule")
            rule = HouseRule(id=f"rule-{bill}", bill_type=bill, split=split, source_text=reason)
            rest = [r for r in names if r not in split]
            even = (1 - sum(split.values())) / len(rest) if rest else 0.0
            pcts = ", ".join(f"{names[r]} {split.get(r, even) * 100:g}%" for r in names)
            return rule_vote(bill, rule, f"House rule: {bill} split {pcts}", f"Since {reason},")

        def remove_rule(args: dict) -> ToolOutput:
            bill = rule_bill_of(args)
            vote_open(bill)
            current = store.house_rule(bill)
            if current is None:
                raise ValueError(f"{bill} is already split evenly")
            rule = HouseRule(id=current.id, bill_type=bill, split={}, source_text="back to an even split")
            return rule_vote(bill, rule, f"House rule: {bill} back to an even split", "Going back to even,")

        def start_bill(args: dict) -> ToolOutput:
            bill = bill_of(args)
            return ToolOutput({"started": bill}, self._start_bill(bill))

        def group_affordability(args: dict) -> ToolOutput:
            price = args.get("price")
            price = float(price) if isinstance(price, (int, float)) and not isinstance(price, bool) else None
            item = args.get("item") if isinstance(args.get("item"), str) else None
            one_off = shares_of(args) if args.get("shares") else None
            reason = str(args.get("reason") or "").strip()[:120] or None
            return ToolOutput({"proposed": True}, self._afford(text, price, item, months_of(args),
                                                               self._context(), one_off, reason))

        bill_param = {"bill": {"type": "string", "enum": sorted(BILL_EVENTS)}}
        rule_param = {"bill": {"type": "string", "enum": RULE_BILLS,
                               "description": "purchase = the default split for shared buys"}}
        shares_param = {"type": "object", "additionalProperties": {"type": "number"},
                        "description": "Roommate name -> percent, e.g. {\"Alex\": 40, \"Sam\": 30, \"Jordan\": 30}."}
        price_params = {"item": {"type": "string", "description": "What they want, singular, e.g. couch."},
                        "price": {"type": "number", "description": "Total USD, as a roommate stated it."},
                        "months": {"type": "integer", "description": "Spread the cost over this many months."},
                        "shares": shares_param | {"description": "Only for an uneven split of THIS purchase "
                                                  "(e.g. Alex pays 50% since it's in Alex's room). Omit to use "
                                                  "the house purchase rule or an even split."},
                        "reason": {"type": "string", "description": "Why the split is uneven, in their words."}}
        return [
            AgentTool("house_status", "Shared house facts: today, bills (amount, due, payer, house rule), "
                      "proposals with who approved / is still pending, and who owes whom.", {}, house_status),
            AgentTool("split_bill", "Split a bill by the house rules (read-only).",
                      bill_param | {"amount": {"type": "number", "description": "Override the bill amount."}},
                      split_bill, ("bill",)),
            AgentTool("what_if_purchase", "Read-only what-if: per-person monthly cost and each roommate's "
                      "ok/tight/no for a purchase over N months. Proposes nothing.",
                      price_params, what_if_purchase, ("price",)),
            AgentTool("can_cover", "Ask a roommate's personal agent if they can cover an amount by a date. "
                      "Returns only ok/tight/no and, if no, the earliest date they can.",
                      {"roommate": {"type": "string"}, "amount": {"type": "number"},
                       "by_date": {"type": "string", "description": "YYYY-MM-DD, default today."},
                       "purpose": {"type": "string"}}, can_cover, ("roommate", "amount")),
            AgentTool("propose_rule", "ACTION: put a house rule to a vote: how a bill is split and why. "
                      "Unlisted roommates split the rest evenly. Posts a preview of the dollar split.",
                      rule_param | {"shares": shares_param,
                                    "reason": {"type": "string", "description": "Why, in their words, e.g. "
                                               "Alex has the master bedroom."}},
                      propose_rule, ("bill", "shares")),
            AgentTool("remove_rule", "ACTION: put going back to an even split of a bill to a vote.",
                      rule_param, remove_rule, ("bill",)),
            AgentTool("start_bill", "ACTION: split the bill, ask personal agents, and post the payment "
                      "proposal (with any payday fronting) for approval.", bill_param, start_bill, ("bill",)),
            AgentTool("group_affordability", "ACTION: propose buying something together. Picks the plan "
                      "(up front, or spread over months), posts it and asks for yeses.",
                      price_params, group_affordability),
        ]


def store_merchants() -> list[str]:
    return fixtures.scenario().merchants  # merchants are scenario data, not a store table in P0
