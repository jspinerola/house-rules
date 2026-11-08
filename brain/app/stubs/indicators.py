"""Fixed indicator values from fixtures/expected.json; profile runs the pure pattern helpers."""
from __future__ import annotations

from contracts.models import Indicator, Profile, Recurring
from wellness import patterns

from .. import fixtures, registry


class StubIndicators:
    def compute(self, rid: str) -> dict[str, Indicator]:
        return {k: v.model_copy() for k, v in fixtures.expected().indicators[rid].items()}

    def profile(self, rid: str) -> Profile:
        store = registry.get("store")
        r = store.get_roommate(rid)
        tx = [{"date": t.date, "category": t.category, "description": t.description, "amount": t.amount}
              for t in store.transactions(rid)]
        pays = 1.0 if r.pay.schedule == "monthly" else 26 / 12
        return Profile(**patterns.income_pattern(tx, r.pay.amount, pays),
                       recurring=[Recurring(**x) for x in patterns.recurring_charges(tx, store.today())],
                       spend_trend_pct=0.0, preferences=store.get_preferences(rid),
                       indicators=self.compute(rid))
