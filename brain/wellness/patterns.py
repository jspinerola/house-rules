"""House Rules addition to the PNC workshop toolkit: patterns in a customer's transactions.

Extends wellness/profile.py (same transaction dicts: date, category, amount, description).
Pure, deterministic code; the LLM only explains the results.
"""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median

# House bills (handled by proposals), money in, and roommate transfers are not personal recurring charges.
NOT_RECURRING = {"rent", "utilities", "income", "transfer"}
PAY_TOLERANCE = 0.01      # a deposit within 1% of the pay rule amount is payroll
AMOUNT_TOLERANCE = 0.05   # recurring charges repeat within 5% of their typical amount
SIDE_INCOME_SHARE = 0.10  # side income >= 10% of monthly regular pay -> "steady_plus_side"


def months_of_history(tx: list[dict]) -> int:
    return max(len({t["date"][:7] for t in tx}), 1)


def income_pattern(tx: list[dict], pay_amount: float, pays_per_month: float) -> dict:
    """Split income deposits into payroll (matches the pay rule) and side income (gigs, tips)."""
    income = [t for t in tx if t["category"] == "income" and t["amount"] > 0]
    payroll = [t for t in income if abs(t["amount"] - pay_amount) <= pay_amount * PAY_TOLERANCE]
    side = [t for t in income if t not in payroll]
    side_monthly = round(sum(t["amount"] for t in side) / months_of_history(tx), 2)
    regular_monthly = pay_amount * pays_per_month
    if not payroll:
        pattern = "irregular"
    elif side_monthly >= regular_monthly * SIDE_INCOME_SHARE:
        pattern = "steady_plus_side"
    else:
        pattern = "steady"
    return {"income_pattern": pattern, "regular_pay": round(pay_amount, 2) if payroll else 0.0,
            "side_income_monthly": side_monthly}


def _next_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(y, m, min(d.day, 28))


def recurring_charges(tx: list[dict], today: str) -> list[dict]:
    """Charges with the same description and amount in at least 2 of the last 3 calendar months."""
    t0 = date.fromisoformat(today)
    window = {f"{t0.year}-{t0.month:02d}"}
    d = t0.replace(day=1)
    for _ in range(2):
        d = (d - timedelta(days=1)).replace(day=1)
        window.add(f"{d.year}-{d.month:02d}")
    by_desc: dict[str, list[dict]] = {}
    for t in tx:
        if t["amount"] < 0 and t["category"] not in NOT_RECURRING and t["date"][:7] in window:
            by_desc.setdefault(t.get("description", ""), []).append(t)
    out = []
    for name, rows in by_desc.items():
        typical = median(-r["amount"] for r in rows)
        steady = [r for r in rows if abs(-r["amount"] - typical) <= typical * AMOUNT_TOLERANCE]
        if not name or len({r["date"][:7] for r in steady}) < 2 or len(steady) != len(rows):
            continue
        last = date.fromisoformat(max(r["date"] for r in steady))
        nxt = _next_month(last)
        while nxt <= t0:
            nxt = _next_month(nxt)
        out.append({"name": name, "amount": round(-steady[-1]["amount"], 2), "next_date": nxt.isoformat()})
    return sorted(out, key=lambda r: (r["next_date"], r["name"]))


def due_between(recurring: list[dict], after: str, until: str) -> float:
    """Total of recurring charges whose next date falls in (after, until]."""
    return round(sum(r["amount"] for r in recurring if after < r["next_date"] <= until), 2)


def spend_trend_pct(tx: list[dict], today: str, avg_monthly_spending: float) -> float:
    """Last 30 days of spending vs the average month, in percent (+ = spending more)."""
    start = (date.fromisoformat(today) - timedelta(days=30)).isoformat()
    recent = -sum(t["amount"] for t in tx if t["amount"] < 0 and t["date"] > start
                  and t["category"] not in ("debt_payments", "transfer"))
    if not avg_monthly_spending:
        return 0.0
    return round((recent - avg_monthly_spending) / avg_monthly_spending * 100, 1)
