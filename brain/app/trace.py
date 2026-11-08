"""trace.log(agent, event, detail): every agent hand-off lands on the dashboard."""
from __future__ import annotations

from datetime import datetime, timezone

from contracts.models import TraceEvent

from . import registry


def log(agent: str, event: str, detail: str) -> TraceEvent:
    e = TraceEvent(ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                   agent=agent, event=event, detail=detail)
    registry.get("store").add_trace(e)
    return e
