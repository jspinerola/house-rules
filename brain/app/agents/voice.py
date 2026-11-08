"""Shared wording step for agents: code writes the draft, the LLM says it in the agent's voice,
the Auditor checks it. Blocked twice -> the code draft (if it passes) -> a safe template."""
from __future__ import annotations

from .. import registry, trace
from .auditor import numbers_in

RULES = """You are part of House Rules, a roommate money agent in iMessage.
- Never compute numbers. Quote tool output only; keep every number and date exactly as given.
- Never repeat a roommate's balance, income or merchants in the group. Only ok, tight, no, or a date.
- Every money movement is a proposal until the required people reply yes.
- Never claim anything about anyone's money (ok, fine, safe, short) unless the draft says it.
- Refer to roommates by name or they/them; never guess he/she.
- Keep iMessage replies to 1-3 sentences."""

PERSONAS = {
    "house": """VOICE: You are the house manager, a fixture of this roommates' group chat, not a bank bot.
You keep the place running: warm, direct, a little dry humor. Use first names, react to what people
actually said, and own the next step ("I'll set it up, just need your yeses"). Sound like a person
texting, not a form letter. Don't open every message with a greeting. Never preachy, never list
features unless someone asks what you do.""",
    "personal": """VOICE: You are this roommate's private money friend in their DM. Candid, on their side,
low-key and reassuring. Talk to them directly by first name when it fits. Never discuss other
roommates' finances.""",
}

# Small talk: the draft is only a fallback, so the LLM answers what was actually said.
CHAT_HOW = ("Answer the latest message naturally, in your voice. The draft is only a "
            "fallback; use its content only if they seem new, confused, or ask what you do. 1-2 sentences.")

SAFE = "I have an update for you. The details are in the house view."


def _persona(agent: str, audience: str) -> str:
    if not agent.startswith("personal"):
        return PERSONAS["house"]
    name = next((r.name for r in registry.get("store").roommates() if r.id == audience), audience)
    return PERSONAS["personal"] + f"\nThis DM is with {name}; you are talking to {name} only."


def speak(agent: str, flow: str, draft: str, allowed: set[float], audience: str,
          context: str | None = None) -> str:
    """Word `draft` in the agent's voice. `context` is the recent chat / message being answered;
    numbers the user typed themselves are allowed back (the auditor still blocks private figures)."""
    llm, auditor = registry.get("llm"), registry.get("auditor")
    allowed = set(allowed) | (set(numbers_in(context)) if context else set())
    prompt = ""
    if context:
        prompt += f"CONVERSATION (most recent last):\n{context}\n\n"
    how = (CHAT_HOW if flow == "small_talk" else
           "Write the reply in your own voice. Keep every number, date and decision in the draft "
           "exactly; you may add a short human touch (react, use names). If they asked something the "
           "draft doesn't answer, don't answer it or guess; just give the draft. 1-3 sentences.")
    prompt += f"Allowed numbers: {sorted(allowed)}\n{how}\nDRAFT: {draft}"
    messages = [
        {"role": "system", "content": f"{RULES}\n{_persona(agent, audience)}\nFLOW:{flow}"},
        {"role": "user", "content": prompt},
    ]
    for attempt in range(2):
        text = llm.chat(messages).text.strip()
        result = auditor.check(text, allowed, audience)
        if result.ok and text:
            trace.log(agent, "replied", f"to {audience}: {text if audience == 'group' else text[:80]}")  # group text is public
            return text
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "The auditor blocked that: " + "; ".join(result.reasons)
                      + f"\nUse only the allowed numbers.\nDRAFT: {draft}"}]
    if auditor.check(draft, allowed, audience).ok:
        trace.log("auditor", "fallback", f"{agent} -> {audience}: code template used")
        return draft
    trace.log("auditor", "fallback", f"{agent} -> {audience}: safe template used")
    return SAFE
