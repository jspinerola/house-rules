"""Hands out the stub or real implementation of each module, chosen by <MODULE>_MODE.

Every module reaches its neighbours only through `get(name)`; nobody imports another
module's real code. All flags default to `stub`.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
from typing import Any

from contracts.interfaces import PROTOCOLS

ENV: dict[str, str] = {
    "store": "DB_MODE", "indicators": "INDICATORS_MODE", "tools": "TOOLS_MODE",
    "proposals": "PROPOSALS_MODE", "auditor": "AUDITOR_MODE", "llm": "LLM_MODE",
    "personal": "PERSONAL_MODE", "house": "HOUSE_MODE", "nessie": "NESSIE_MODE",
    "treasurer": "TREASURER_MODE", "outbox": "OUTBOX_MODE",
}

# "module:Class" per mode; None = planned but not implemented yet.
IMPLS: dict[str, dict[str, str | None]] = {
    "store": {"stub": "app.stubs.store:StubStore", "sqlite": "app.db:SqliteStore", "tiger": None},
    "indicators": {"stub": "app.stubs.indicators:StubIndicators", "real": "app.indicators:Indicators"},
    "tools": {"stub": "app.stubs.tools:StubTools", "real": "app.tools:Tools"},
    "proposals": {"stub": "app.stubs.proposals:StubProposals", "real": "app.proposals:Proposals"},
    "auditor": {"stub": "app.stubs.auditor:StubAuditor", "real": "app.agents.auditor:Auditor"},
    "llm": {"stub": "app.stubs.llm:StubLLM", "grok": "app.agents.llm:GrokLLM"},
    "personal": {"stub": "app.stubs.personal:StubPersonal", "real": "app.agents.personal:PersonalAgent"},
    "house": {"stub": "app.stubs.house:StubHouse", "real": "app.agents.house:HouseAgent"},
    "nessie": {"stub": "app.stubs.nessie:StubNessie", "live": "app.nessie:LiveNessie"},
    "treasurer": {"stub": "app.stubs.treasurer:StubTreasurer", "real": "app.treasurer:Treasurer"},
    "outbox": {"stub": "app.stubs.outbox:StubOutbox", "http": "app.outbox:HttpOutbox"},
}

# `real` means the module's non-stub implementation, so "flip everything to real" works.
REAL_ALIAS = {"store": "sqlite", "llm": "grok", "nessie": "live", "outbox": "http"}

_cache: dict[tuple[str, str], Any] = {}


def mode(name: str) -> str:
    m = os.environ.get(ENV[name], "stub").strip().lower() or "stub"
    if m == "real":
        m = REAL_ALIAS.get(name, "real")
    if m not in IMPLS[name]:
        raise ValueError(f"{ENV[name]}={m!r}; expected one of {sorted(IMPLS[name])}")
    return m


def modes() -> dict[str, str]:
    return {name: mode(name) for name in IMPLS}


def available(name: str, m: str) -> bool:
    """True when the implementation for (name, mode) exists in the codebase."""
    path = IMPLS[name].get(REAL_ALIAS.get(name, m) if m == "real" else m)
    if not path:
        return False
    return importlib.util.find_spec(path.split(":")[0]) is not None


def _load(name: str, m: str) -> Any:
    path = IMPLS[name][m]
    if path is None:
        raise NotImplementedError(f"{ENV[name]}={m} is not implemented yet; use stub")
    mod_name, cls_name = path.split(":")
    obj = getattr(importlib.import_module(mod_name), cls_name)()
    proto = PROTOCOLS[name]
    if not isinstance(obj, proto):
        raise TypeError(f"{path} does not satisfy {proto.__name__}")
    return obj


def get(name: str) -> Any:
    m = mode(name)
    key = (name, m)
    if key not in _cache:
        _cache[key] = _load(name, m)
    return _cache[key]


def reset() -> None:
    """Drop every cached instance (modes are re-read on the next get)."""
    _cache.clear()
