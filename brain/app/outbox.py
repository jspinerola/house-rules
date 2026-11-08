"""OUTBOX_MODE=http: push proactive messages to the gateway's POST /send."""
from __future__ import annotations

import os
import urllib.request

from contracts.models import Reply


class HttpOutbox:
    def __init__(self) -> None:
        self.url = os.environ.get("GATEWAY_URL", "http://localhost:8787").rstrip("/") + "/send"

    def send(self, reply: Reply) -> None:
        body = reply.model_dump_json(by_alias=True).encode()
        req = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as r:  # errors propagate to the caller
            if r.status != 200:
                raise RuntimeError(f"gateway /send returned {r.status}")
