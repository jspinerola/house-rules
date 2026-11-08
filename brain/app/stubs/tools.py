"""Returns the expected.json answers; unknown inputs fall back to the nearest scripted case."""
from __future__ import annotations

from contracts.models import Affordability, CoverAnswer, HouseRule, PaydayPlan, SplitResult

from .. import fixtures, registry


class StubTools:
    def split_bill(self, bill_type: str, amount: float, rule: HouseRule | None = None) -> SplitResult:
        if rule is None:
            for c in fixtures.expected().split_bill:
                if c.bill_type == bill_type:
                    return c.expect.model_copy()
            rule = registry.get("store").house_rule(bill_type)  # e.g. purchases: no scripted case
        # A candidate rule, or an unscripted bill: same math as the real split.
        ids = list(fixtures.expected().next_payday)
        fixed = {rid: round(amount * f, 2) for rid, f in (rule.split if rule else {}).items()}
        rest = [rid for rid in ids if rid not in fixed]
        each = round((amount - sum(fixed.values())) / len(rest), 2) if rest else 0.0
        shares = {rid: fixed.get(rid, each) for rid in ids}
        if rest:
            shares[rest[0]] = round(shares[rest[0]] + amount - sum(shares.values()), 2)
        return SplitResult(shares=shares)

    def can_cover(self, rid: str, amount: float, date: str) -> CoverAnswer:
        for c in fixtures.expected().can_cover:
            if c.roommate_id == rid and abs(c.amount - amount) < 0.01:
                return c.expect.model_copy()
        return CoverAnswer(level="ok")

    def payday_plan(self, rid: str, amount: float) -> PaydayPlan:
        for c in fixtures.expected().payday_plan:
            if c.roommate_id == rid:
                return c.expect.model_copy()
        raise KeyError(f"stub has no payday plan for {rid!r}")

    def group_affordability(self, item: str, price: float, months_options: tuple[int, ...] = (1, 3),
                            shares: dict[str, float] | None = None) -> Affordability:
        return fixtures.expected().group_affordability[0].expect.model_copy(deep=True)

    def next_payday(self, rid: str, after: str) -> str | None:
        d = fixtures.expected().next_payday[rid]
        return d if d > after else None
