"""Auditor (AUDITOR_MODE=real): code, not an LLM, between every agent and the chat.

Blocks (1) any number not in `allowed_numbers` (gathered from this turn's tool outputs) and
(2) any roommate's balance or income in a group message, or another roommate's in a DM.
Dates ("2026-12-16", "12/16", "16th") are not amounts and are ignored.
Builds on the workshop's wellness/validation.py idea of checking numbers before explaining.
"""
from __future__ import annotations

import re

from contracts.models import AuditResult

from .. import registry, trace

DATES = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{1,2}(?:st|nd|rd|th)\b"
                   r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b(?:,?\s+\d{4})?",
                   re.I)
NUMBER = re.compile(r"(?<![\w.])\$?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?")
TOL = 0.005


def numbers_in(text: str) -> list[float]:
    stripped = DATES.sub(" ", text)
    return [float(m.group(1).replace(",", "") + (m.group(2) or "")) for m in NUMBER.finditer(stripped)]


def _private_figures(exclude: str | None) -> dict[float, str]:
    """Balances and incomes of every roommate except `exclude` (the DM's owner)."""
    store, nessie = registry.get("store"), registry.get("nessie")
    out: dict[float, str] = {}
    for r in store.roommates():
        if r.id == exclude:
            continue
        out[round(nessie.balance(r.id), 2)] = f"{r.name}'s balance"
        out[round(r.pay.amount, 2)] = f"{r.name}'s pay"
        out[round(r.monthly_income, 2)] = f"{r.name}'s income"
    return out


class Auditor:
    def check(self, text: str, allowed_numbers: set[float], audience: str) -> AuditResult:
        reasons: list[str] = []
        private = _private_figures(None if audience == "group" else audience)
        for n in numbers_in(text):
            leaked = next((label for v, label in private.items() if abs(v - n) < TOL), None)
            if leaked:
                reasons.append(f"reveals {leaked} ({n:g}) to {audience}")
            elif not any(abs(a - n) < TOL for a in allowed_numbers):
                reasons.append(f"number {n:g} is not from a tool output")
        if reasons:
            trace.log("auditor", "blocked", f"to {audience}: {'; '.join(reasons)}")
        return AuditResult(ok=not reasons, reasons=reasons)
