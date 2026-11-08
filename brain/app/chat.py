"""POST /chat handling: resolve sender, approvals to Proposals, the rest to the right agent."""
from __future__ import annotations

from contracts.models import ChatIn, ChatOut, DMTarget, GroupTarget, Proposal, Reply

from . import registry


def _approval_text(name: str, p: Proposal, names: dict[str, str]) -> str:
    if p.status == "rejected":
        return f"{name} said no, so {p.title} is off. What should change?"
    if p.status == "failed":
        return f"{p.title} was approved but a payment failed. The treasurer is reporting back."
    if p.status in ("approved", "executed") and p.flow == "rule":
        return f"Thanks {name}. Everyone agreed, so it's official: {p.title}."
    if p.status in ("approved", "executed"):
        return f"Thanks {name}. Everyone approved {p.title}, so the treasurer is sending it."
    waiting = [names[r] for r, v in p.approvals.items() if v == "pending"]
    return f"Got it, {name}. Still waiting on {', '.join(waiting)}."


def handle(msg: ChatIn) -> ChatOut:
    store = registry.get("store")
    sender = store.by_handle(msg.sender_handle)
    if sender is None:
        target = GroupTarget() if msg.chat_type == "group" else DMTarget(roommate_id=msg.sender_handle)
        return ChatOut(replies=[Reply(target=target, text="I don't know you yet.")])

    here = GroupTarget() if msg.chat_type == "group" else DMTarget(roommate_id=sender.id)
    proposals = registry.get("proposals")
    if proposals.parse(msg.text) and store.pending_for(sender.id):
        p = proposals.record_reply(sender.id, msg.text)
        if p is not None:
            names = {r.id: r.name for r in store.roommates()}
            return ChatOut(replies=[Reply(target=here, text=_approval_text(sender.name, p, names))])

    if msg.chat_type == "group":
        return ChatOut(replies=registry.get("house").on_message(sender.id, msg.text))
    return ChatOut(replies=registry.get("personal").dm(sender.id, msg.text))
