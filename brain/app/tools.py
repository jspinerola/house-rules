"""Specialist tools the house agent calls (TOOLS_MODE=real). Pure code, no LLM.

Rules (REQUIREMENTS M3, docs/RULES_AND_PROFILES.md):
  can_cover: cash at the next payday also subtracts that roommate's recurring charges due before it.
    ok = cash >= max($200, min_buffer) + savings_monthly; tight = >= $0; no = negative.
    ok drops to tight when runway_days is "risk". `reason` (DM-only) says what made it not ok.
  payday_plan: fronter = roommate with the highest buffer_after(amount) whose front_cap allows it;
    repay = day after payday.
  group_affordability: try each months option in order; first plan where nobody is "no" wins.
    Each roommate's share comes from one-off `shares`, else the "purchase" house rule, else even.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from contracts.models import (
    Affordability, AffordPlan, CoverAnswer, CoverReason, HouseRule, Level, PaydayPlan, SplitResult,
)
from wellness import patterns

from . import registry

OK_FLOOR = 200.0
MAX_PAYDAYS_AHEAD = 6
COMMITTED = ("pending", "approved", "executed")


def _d(s: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"invalid date {s!r}") from e


def _money(amount: float, label: str = "amount") -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
        raise ValueError(f"{label} must be a finite number")
    if amount < 0:
        raise ValueError(f"{label} must be >= 0")
    return float(amount)


def _add_month(d: date, day: int) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, day)


class Tools:
    # ----- helpers -----

    def next_payday(self, rid: str, after: str) -> str | None:
        pay = registry.get("store").get_roommate(rid).pay  # KeyError on unknown rid
        a = _d(after)
        if pay.schedule == "monthly":
            if pay.day is None:
                raise ValueError(f"{rid}: monthly pay rule needs a day")
            cand = date(a.year, a.month, pay.day)
            return (cand if cand > a else _add_month(a, pay.day)).isoformat()
        if pay.anchor is None:
            raise ValueError(f"{rid}: biweekly pay rule needs an anchor")
        steps = (a - _d(pay.anchor)).days // 14 + 1
        return (_d(pay.anchor) + timedelta(days=14 * steps)).isoformat()

    def _committed_out(self, rid: str, until: str) -> float:
        """Money already promised out of rid's account on or before `until`."""
        return round(sum(
            leg.amount
            for p in registry.get("store").proposals() if p.status in COMMITTED
            for leg in p.legs if leg.status == "pending" and leg.from_ == rid and leg.date <= until
        ), 2)

    def _recurring_until(self, rid: str, until: str) -> float:
        """Recurring personal charges (subscriptions, phone) due after today, on or before `until`."""
        store = registry.get("store")
        prof = registry.get("indicators").profile(rid)
        return patterns.due_between([r.model_dump() for r in prof.recurring], store.today(), until)

    def _projection(self, rid: str, amount: float, by: str) -> tuple[float, str]:
        """Cash left at the next payday after `by`, crediting paydays up to `by`."""
        store = registry.get("store")
        pay = store.get_roommate(rid).pay  # KeyError on unknown rid
        amount = _money(amount)
        by_s = _d(by).isoformat()
        cash = registry.get("nessie").balance(rid) - amount
        d = self.next_payday(rid, store.today())
        while d is not None and d <= by_s:
            cash += pay.amount
            d = self.next_payday(rid, d)
        if d is None:
            raise ValueError(f"no next payday horizon for {rid!r}")
        return round(cash - self._committed_out(rid, d) - self._recurring_until(rid, d), 2), d

    def buffer_after(self, rid: str, amount: float) -> float:
        return self._projection(rid, amount, registry.get("store").today())[0]

    # ----- protocol -----

    def split_bill(self, bill_type: str, amount: float, rule: HouseRule | None = None) -> SplitResult:
        amount = _money(amount)
        store = registry.get("store")
        ids = [r.id for r in store.roommates()]
        rule = rule if rule is not None else store.house_rule(bill_type)
        fixed = {rid: round(amount * frac, 2) for rid, frac in (rule.split if rule else {}).items()}
        rest = [rid for rid in ids if rid not in fixed]
        each = round((amount - sum(fixed.values())) / len(rest), 2) if rest else 0.0
        shares = {rid: fixed.get(rid, each) for rid in ids}
        if rest:  # put rounding cents on the first evenly-split roommate
            shares[rest[0]] = round(shares[rest[0]] + amount - sum(shares.values()), 2)
        return SplitResult(shares=shares)

    def can_cover(self, rid: str, amount: float, date: str) -> CoverAnswer:
        cash, horizon = self._projection(rid, amount, date)
        prefs = registry.get("store").get_preferences(rid)
        cushion = max(OK_FLOOR, prefs.min_buffer or 0.0)
        floor = cushion + (prefs.savings_monthly or 0.0)
        level: Level = "ok" if cash >= floor else "tight" if cash >= 0 else "no"
        reason: CoverReason | None = None
        if level == "tight":
            reason = ("savings_goal" if cash >= cushion else "cushion" if cash >= OK_FLOOR
                      else "upcoming_bills" if cash + self._recurring_until(rid, horizon) >= OK_FLOOR
                      else None)
        if level == "ok" and registry.get("indicators").compute(rid)["runway_days"].status == "risk":
            level, reason = "tight", "runway"
        if level != "no":
            return CoverAnswer(level=level, reason=reason)
        pay = registry.get("store").get_roommate(rid).pay
        d = horizon
        for _ in range(MAX_PAYDAYS_AHEAD):
            cash += pay.amount
            if cash >= 0:
                return CoverAnswer(level="no", earliest_date=d)
            d = self.next_payday(rid, d)
            if d is None:
                break
        return CoverAnswer(level="no", earliest_date=None)

    def payday_plan(self, rid: str, amount: float) -> PaydayPlan:
        amount = _money(amount)
        store = registry.get("store")
        store.get_roommate(rid)  # KeyError on unknown rid
        others = [r.id for r in store.roommates() if r.id != rid
                  and (store.get_preferences(r.id).front_cap is None
                       or store.get_preferences(r.id).front_cap >= amount)]
        if not others:
            raise ValueError(f"nobody can front {amount:.2f}: every roommate's front cap is lower")
        fronter = max(others, key=lambda o: self.buffer_after(o, amount))
        payday = self.next_payday(rid, store.today())
        if not payday:
            raise ValueError(f"no next payday for {rid!r}")
        return PaydayPlan(fronter=fronter, repay_date=(_d(payday) + timedelta(days=1)).isoformat())

    def purchase_shares(self, price: float, shares: dict[str, float] | None = None) -> dict[str, float]:
        """Dollar share of a purchase per roommate: one-off fractions, else the purchase rule, else even."""
        rule = None
        if shares is not None:
            rule = HouseRule(id="one-off", bill_type="purchase", split=shares, source_text="one-off split")
        return self.split_bill("purchase", price, rule=rule).shares

    def group_affordability(self, item: str, price: float, months_options: tuple[int, ...] = (1, 3),
                            shares: dict[str, float] | None = None) -> Affordability:
        price = _money(price, "price")
        store = registry.get("store")
        ids = [r.id for r in store.roommates()]
        today = store.today()
        owed = self.purchase_shares(price, shares)
        uneven = max(owed.values()) - min(owed.values()) > 0.011  # rounding cents are still even
        answers: dict[str, Level] = {}
        for months in months_options:
            even = round(price / len(ids) / months, 2)
            monthly = {rid: round(owed[rid] / months, 2) for rid in ids} if uneven else {rid: even for rid in ids}
            answers = {rid: self.can_cover(rid, monthly[rid], today).level for rid in ids}
            if "no" not in answers.values():
                return Affordability(answers=answers, plan=AffordPlan(
                    months=months, per_person_monthly=even, monthly=monthly if uneven else {}))
        return Affordability(answers=answers, plan=None)
