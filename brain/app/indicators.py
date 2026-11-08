"""Per-roommate indicators (INDICATORS_MODE=real).

Adapts our store + bank data into the PNC workshop profile shape and reuses
wellness.profile.build_profile + wellness.metrics.compute_metrics for the 8 workshop
indicators, then adds runway_days, rent_to_income, days_to_payday and buffer_after.
"""
from __future__ import annotations

from datetime import date

from contracts.models import Indicator, IndicatorStatus
from wellness.metrics import _status, compute_metrics
from wellness.profile import build_profile

from . import registry


def _customer(rid: str) -> dict:
    """Workshop customer dict: accounts (checking balance from the bank) + history."""
    store = registry.get("store")
    r = store.get_roommate(rid)
    balance = registry.get("nessie").balance(rid)
    accounts = [{"id": a.id, "type": a.type, "name": a.name,
                 "balance": balance if a.type == "checking" else a.balance,
                 **({"credit_limit": a.credit_limit} if a.credit_limit is not None else {})}
                for a in r.accounts]
    txns = [{"date": t.date, "category": t.category, "amount": t.amount} for t in store.transactions(rid)]
    return {"customer_id": rid, "monthly_income": r.monthly_income, "accounts": accounts, "transactions": txns}


class Indicators:
    def compute(self, rid: str) -> dict[str, Indicator]:
        """Deterministic health metrics for one roommate. Never calls an LLM.

        Uses only that roommate's store history + Nessie balance, plus shared
        house facts (rent bill / clock). Unknown rid raises KeyError via Store.
        """
        store, tools = registry.get("store"), registry.get("tools")
        store.get_roommate(rid)  # fail closed on unknown / injection-style ids
        today = store.today()
        profile = build_profile(_customer(rid))
        metrics = compute_metrics(profile)
        out: dict[str, Indicator] = {}
        for key, value in metrics["values"].items():
            status = metrics["status"][key]
            if value is None or status == "unknown":
                raise ValueError(f"indicator {key} for {rid} is missing input data")
            out[key] = Indicator(value=float(value), status=status, inputs={})

        balance = float(registry.get("nessie").balance(rid))
        spend = float(profile["avg_monthly_spending"])
        if not spend:
            raise ValueError(f"indicator runway_days for {rid} needs spending history")
        runway = round(balance / (spend / 30), 1)
        share = float(tools.split_bill("rent", store.bill("rent").amount).shares[rid])
        income = float(profile["monthly_income"])
        if not income:
            raise ValueError(f"indicator rent_to_income for {rid} needs monthly_income")
        payday = tools.next_payday(rid, today)
        if not payday:
            raise ValueError(f"no next payday for {rid!r} after {today}")
        days = float((date.fromisoformat(payday) - date.fromisoformat(today)).days)
        buffer = round(balance - share, 2)
        days_status: IndicatorStatus = "good" if runway >= days + 7 else "watch" if runway >= days else "risk"

        out["runway_days"] = Indicator(value=runway, status=_status(runway, 30, 14),
                                       inputs={"balance": balance, "avg_monthly_spending": spend})
        out["rent_to_income"] = Indicator(value=round(share / income, 4),
                                          status=_status(share / income, 0.3, 0.4, False),
                                          inputs={"rent_share": share, "monthly_income": income})
        out["days_to_payday"] = Indicator(value=days, status=days_status,
                                          inputs={"next_payday": payday, "runway_days": runway})
        out["buffer_after"] = Indicator(value=buffer, status=_status(buffer, 200, 0),
                                        inputs={"amount": share, "balance": balance})
        return out
