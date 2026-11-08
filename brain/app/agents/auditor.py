"""Auditor (AUDITOR_MODE=real): code, not an LLM, between every agent and the chat.

Blocks (1) any number not in `allowed_numbers` (gathered from this turn's tool outputs) and
(2) any roommate's balance or income in a group message, or another roommate's in a DM.
Profile figures (side income, recurring charges, preference amounts) are private too, but only block when they are
not also a tool output this turn (Kevin's $45 phone plan vs Xander's $45 electric share).
Dates ("2026-12-16", "12/16", "16th") are not amounts and are ignored.
Builds on the workshop's wellness/validation.py idea of checking numbers before explaining.
"""
from __future__ import annotations

import re

from contracts.models import AuditResult

from .. import registry, trace

DATES = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b(?:0?[1-9]|1[0-2])-\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)\b"
                   r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b(?:,?\s+\d{4})?",
                   re.I)
NUMBER = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
TOL = 0.005


def numbers_in(text: str) -> list[float]:
    stripped = DATES.sub(" ", text)
    return [float(m.group(1).replace(",", "") + (m.group(2) or "")) for m in NUMBER.finditer(stripped)]


def _figures(rid: str, name: str) -> tuple[dict[float, str], dict[float, str]]:
    """(hard, soft) private figures for one roommate: hard always blocks, soft blocks unless allowed."""
    store, nessie = registry.get("store"), registry.get("nessie")
    r = store.get_roommate(rid)
    hard = {round(nessie.balance(rid), 2): f"{name}'s balance", round(r.pay.amount, 2): f"{name}'s pay",
            round(r.monthly_income, 2): f"{name}'s income"}
    prefs = store.get_preferences(rid)
    soft = {round(v, 2): f"{name}'s {label}" for v, label in (
        (prefs.min_buffer, "cushion"), (prefs.savings_monthly, "savings goal"), (prefs.front_cap, "front cap"))
        if v}
    prof = registry.get("indicators").profile(rid)
    for c in prof.recurring:
        soft.setdefault(round(c.amount, 2), f"{name}'s {c.name} charge")
    if prof.side_income_monthly:
        soft[round(prof.side_income_monthly, 2)] = f"{name}'s side income"
    return hard, soft


def _private_figures(exclude: str | None) -> tuple[dict[float, str], dict[float, str]]:
    """Private figures of every roommate except `exclude` (the DM's owner), minus the owner's own."""
    hard: dict[float, str] = {}
    soft: dict[float, str] = {}
    own: set[float] = set()
    for r in registry.get("store").roommates():
        h, s = _figures(r.id, r.name)
        if r.id == exclude:
            own |= set(h) | set(s)
            continue
        hard.update(h)
        soft.update(s)
    return ({v: k for v, k in hard.items() if v not in own}, {v: k for v, k in soft.items() if v not in own})


class Auditor:
    def check(self, text: str, allowed_numbers: set[float], audience: str) -> AuditResult:
        reasons: list[str] = []
        hard, soft = _private_figures(None if audience == "group" else audience)
        for n in numbers_in(text):
            allowed = any(abs(a - n) < TOL for a in allowed_numbers)
            leaked = next((label for v, label in hard.items() if abs(v - n) < TOL), None)
            if leaked is None and not allowed:
                leaked = next((label for v, label in soft.items() if abs(v - n) < TOL), None)
            if leaked:
                reasons.append(f"reveals {leaked} ({n:g}) to {audience}")
            elif not allowed:
                reasons.append(f"number {n:g} is not from a tool output")
        if reasons:
            trace.log("auditor", "blocked", f"to {audience}: {'; '.join(reasons)}")
        return AuditResult(ok=not reasons, reasons=reasons)
