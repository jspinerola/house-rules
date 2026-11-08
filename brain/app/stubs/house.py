"""Scripted house agent: rent_due and the couch question create the expected.json proposals."""
from __future__ import annotations

from contracts.models import Ask, DemoEvent, GroupTarget, Reply

from .. import fixtures, registry, trace


def _group(text: str) -> Reply:
    return Reply(target=GroupTarget(), text=text)


class StubHouse:
    def _propose(self, key: str, ask: Ask):
        sp = fixtures.expected().proposals[key]
        legs = [leg.model_copy() for leg in sp.legs]
        for rid in sp.required_approvers:
            trace.log("house", "asked", f"ask_personal {rid}: {ask.purpose}")
            registry.get("personal").ask(rid, ask)
        return registry.get("proposals").create(sp.flow, sp.title, legs, sp.required_approvers)

    def on_event(self, event: DemoEvent) -> list[Reply]:
        scripts = fixtures.expected().scripts
        if event == "rent_due":
            p = self._propose("rent", Ask(amount=800, by_date="2026-11-30", purpose="rent"))
            return [_group(scripts.rent_group)] + registry.get("personal").explain("jordan", p)
        return [_group(scripts.hello_group)]

    def on_message(self, sender_rid: str, text: str) -> list[Reply]:
        scripts = fixtures.expected().scripts
        if "afford" in text.lower():
            self._propose("couch", Ask(amount=133.33, by_date="2026-11-28", purpose="couch"))
            return [_group(scripts.couch_group)]
        return [_group(scripts.hello_group)]
