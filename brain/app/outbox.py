"""OUTBOX_MODE=http: push proactive messages to the gateway's POST /send."""
from __future__ import annotations

import os
import urllib.error
import urllib.request

from contracts.models import Reply


class HttpOutbox:
    def __init__(self) -> None:
        self.url = os.environ.get("GATEWAY_URL", "http://localhost:8787").rstrip("/") + "/send"

    def send(self, reply: Reply) -> None:
        """POST a SendIn body; any delivery failure raises ConnectionError (the API maps it to 502)."""
        body = reply.model_dump_json(by_alias=True).encode()
        req = urllib.request.Request(self.url, body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                status = r.status
        except urllib.error.HTTPError as e:
            raise ConnectionError(f"gateway {self.url} returned {e.code}") from e
        except (urllib.error.URLError, OSError) as e:
            raise ConnectionError(f"gateway {self.url} unreachable: {e}") from e
        if status != 200:
            raise ConnectionError(f"gateway {self.url} returned {status}")
