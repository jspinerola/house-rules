"""Approval reply parsing shared by proposal implementations (AGENTS.md yes/no lists)."""
from __future__ import annotations

import re

from contracts.models import Verdict

YES = {"yes", "y", "yep", "ok", "approve", "\U0001F44D"}
NO = {"no", "n", "nah", "cancel"}


def parse(text: str) -> Verdict | None:
    t = re.sub(r"[.!\s]+$", "", text.strip().lower())
    t = t.replace("️", "")  # emoji variation selector
    for skin in ("\U0001F3FB", "\U0001F3FC", "\U0001F3FD", "\U0001F3FE", "\U0001F3FF"):
        t = t.replace(skin, "")
    if t in YES:
        return "yes"
    if t in NO:
        return "no"
    return None
