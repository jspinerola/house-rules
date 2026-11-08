"""Shared wording step for agents: code writes the draft, the LLM may reword it, the
Auditor checks it. Blocked twice -> the code draft (if it passes) -> a safe template."""
from __future__ import annotations

from .. import registry, trace

RULES = """You are part of House Rules, a roommate money agent in iMessage.
- Never compute numbers. Quote tool output only; keep every number and date exactly as given.
- Never repeat a roommate's balance, income or merchants in the group. Only ok, tight, no, or a date.
- Every money movement is a proposal until the required people reply yes.
- Keep iMessage replies to 1-3 sentences."""

SAFE = "I have an update for you. The details are in the house view."


def speak(agent: str, flow: str, draft: str, allowed: set[float], audience: str) -> str:
    llm, auditor = registry.get("llm"), registry.get("auditor")
    messages = [
        {"role": "system", "content": f"{RULES}\nFLOW:{flow}"},
        {"role": "user", "content": f"Allowed numbers: {sorted(allowed)}\n"
                                    f"Reword for iMessage if it helps.\nDRAFT: {draft}"},
    ]
    for attempt in range(2):
        text = llm.chat(messages).text.strip()
        result = auditor.check(text, allowed, audience)
        if result.ok and text:
            trace.log(agent, "replied", f"to {audience}: {text[:80]}")
            return text
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The auditor blocked that: " + "; ".join(result.reasons)
                      + f"\nUse only the allowed numbers.\nDRAFT: {draft}"}]
    if auditor.check(draft, allowed, audience).ok:
        trace.log("auditor", "fallback", f"{agent} -> {audience}: code template used")
        return draft
    trace.log("auditor", "fallback", f"{agent} -> {audience}: safe template used")
    return SAFE
