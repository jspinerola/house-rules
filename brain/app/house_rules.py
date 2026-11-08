"""Applying an approved `rule` proposal (shared by real and stub Proposals).

A rule proposal moves no money, so the treasurer is never called: on all yeses the rule is
saved (or, when its split is empty, removed) through the Store. See docs/RULES_AND_PROFILES.md.
"""
from __future__ import annotations

from contracts.models import Proposal

from . import registry, trace


def apply(p: Proposal) -> Proposal:
    if p.flow != "rule" or p.rule is None:
        raise ValueError(f"{p.id} is not a rule proposal")
    store = registry.get("store")
    if p.rule.split:
        store.save_house_rule(p.rule.model_copy(update={"confirmed_by": list(p.required_approvers)}))
        trace.log("house", "rule_saved", f"{p.rule.bill_type}: {p.rule.source_text}")
    else:
        store.delete_house_rule(p.rule.bill_type)
        trace.log("house", "rule_removed", f"{p.rule.bill_type}: {p.rule.source_text}")
    p.status = "executed"
    store.save_proposal(p)
    return store.get_proposal(p.id)
