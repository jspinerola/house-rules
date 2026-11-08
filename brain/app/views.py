"""Read models for GET /state (dashboard) and GET /bank/{rid} (bank app)."""
from __future__ import annotations

from contracts.models import BankView, HouseState, Leg, Owe, RoommateStatus, ScheduledPayment

from . import fixtures, registry

LIVE = ("approved", "executed")


def _committed_legs() -> list[Leg]:
    return [leg for p in registry.get("store").proposals() if p.status in LIVE for leg in p.legs]


def house_state() -> HouseState:
    store, tools, nessie = registry.get("store"), registry.get("tools"), registry.get("nessie")
    today = store.today()
    shares = tools.split_bill("rent", store.bill("rent").amount).shares
    roommates = [
        RoommateStatus(id=r.id, name=r.name, balance=nessie.balance(r.id),
                       status=tools.can_cover(r.id, shares[r.id], today).level,
                       next_payday=tools.next_payday(r.id, today) or "")
        for r in store.roommates()
    ]
    owes = [Owe(**{"from": leg.from_}, to=leg.to, amount=leg.amount, due=leg.date)
            for leg in _committed_legs()
            if leg.status == "pending" and leg.to is not None]
    return HouseState(today=today, roommates=roommates, owes=owes,
                      proposals=store.proposals(), trace=store.recent_trace(50))


def bank_view(rid: str) -> BankView:
    store, nessie = registry.get("store"), registry.get("nessie")
    r = store.get_roommate(rid)
    names = {x.id: x.name for x in store.roommates()}
    today = store.today()
    scheduled = []
    for leg in _committed_legs():
        if leg.status != "pending" or leg.date <= today:
            continue
        if leg.from_ == rid:
            dest = names.get(leg.to, leg.payee) if leg.to else leg.payee
            scheduled.append(ScheduledPayment(date=leg.date, description=f"To {dest}", amount=-leg.amount))
        elif leg.to == rid:
            scheduled.append(ScheduledPayment(date=leg.date, description=f"From {names[leg.from_]}",
                                              amount=leg.amount))
    scheduled.sort(key=lambda s: s.date)
    return BankView(bank_name=fixtures.scenario().bank_name, roommate_id=rid, name=r.name,
                    balance=nessie.balance(rid), transactions=nessie.transactions(rid), scheduled=scheduled)
