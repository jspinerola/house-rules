"""Collects proactive messages in memory (tests and stub runs read `sent`)."""
from __future__ import annotations

from contracts.models import Reply


class StubOutbox:
    def __init__(self) -> None:
        self.sent: list[Reply] = []

    def send(self, reply: Reply) -> None:
        self.sent.append(reply)
