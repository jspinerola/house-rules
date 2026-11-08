"""Loads the shared fixtures. Handles can be overridden per roommate via <ID>_HANDLE."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from contracts.models import Expected, Scenario

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


@lru_cache(maxsize=1)
def _raw_scenario() -> dict:
    return json.loads((FIXTURES / "scenario.json").read_text())


def scenario() -> Scenario:
    s = Scenario(**_raw_scenario())
    for r in s.roommates:
        override = os.environ.get(f"{r.id.upper()}_HANDLE", "").strip()
        if override:
            r.handle = override
    return s


@lru_cache(maxsize=1)
def expected() -> Expected:
    return Expected(**json.loads((FIXTURES / "expected.json").read_text()))
