"""Scripted house agent: rent_due and the couch question create the expected.json proposals."""
from __future__ import annotations

from contracts.models import DemoEvent, GroupTarget, Reply

from .. import fixtures, registry, trace


def _group(text: str) -> Reply:
    return Reply(target=GroupTarget(), text=text)


class StubHouse:
    def _propose(self, key: str):
        sp = fixtures.expected().proposals[key]
        legs = [leg.model_copy() for leg in sp.legs]
        for rid in sp.required_approvers:
            trace.log("house", "asked", f"ask_personal {rid}")
        return registry.get("proposals").create(sp.flow, sp.title, legs, sp.required_approvers)

    def on_event(self, event: DemoEvent) -> list[Reply]:
        scripts = fixtures.expected().scripts
        if event == "rent_due":
            p = self._propose("rent")
            return [_group(scripts.rent_group)] + registry.get("personal").explain("jordan", p)
        return [_group(scripts.hello_group)]

    def on_message(self, sender_rid: str, text: str) -> list[Reply]:
        scripts = fixtures.expected().scripts
        if "afford" in text.lower():
            self._propose("couch")
            return [_group(scripts.couch_group)]
        return [_group(scripts.hello_group)]
