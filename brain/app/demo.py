"""Demo control: reset, trigger, advance. The only code that moves the demo clock."""
from __future__ import annotations

from datetime import date

from contracts.models import DemoEvent, Leg, Transaction

from . import fixtures, registry, trace


def reset() -> None:
    # Seed Nessie before touching the store; if seeding fails, keep the old instances so the
    # demo stays on its previous state instead of a half-reset one. The error still propagates.
    before = registry.snapshot()
    registry.reset()
    try:
        registry.get("nessie").seed(fixtures.scenario())
    except Exception:
        registry.restore(before)
        raise
    registry.get("store").reset()


def trigger(event: DemoEvent) -> None:
    trace.log("watcher" if event == "watch" else "house", "triggered", event)
    outbox = registry.get("outbox")
    for reply in registry.get("house").on_event(event):
        outbox.send(reply)


def advance(to: str) -> list[Leg]:
    """Move the clock to `to`, crediting paydays crossed, then run due scheduled legs."""
    store, tools, nessie = registry.get("store"), registry.get("tools"), registry.get("nessie")
    date.fromisoformat(to)  # raises ValueError on a bad date
    today = store.today()
    if to < today:
        raise ValueError(f"cannot move the demo clock back from {today} to {to}")
    paydays: list[tuple[str, str]] = []
    for r in store.roommates():
        d = tools.next_payday(r.id, today)
        while d is not None and d <= to:
            paydays.append((d, r.id))
            d = tools.next_payday(r.id, d)
    for d, rid in sorted(paydays):
        store.set_today(d)
        amount = store.get_roommate(rid).pay.amount
        nessie.deposit(rid, amount, "Payroll deposit")
        store.add_transaction(Transaction(id=f"pay-{rid}-{d}", roommate_id=rid, date=d,
                                          description="Payroll deposit", category="income", amount=amount))
    store.set_today(to)
    trace.log("house", "clock", f"{today} -> {to}, {len(paydays)} paydays")
    return registry.get("treasurer").run_due(to)
