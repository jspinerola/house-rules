"""Tool-calling loop shared by the house and personal agents (LLM_MODE=grok).

The LLM picks tools, reads their JSON results and keeps going until it can answer; code still
does every number. Tool results go back as a plain user message (our ToolCall contract has no
call ids), so this works with any chat model. A tool that returns `replies` ends the turn: that
is an action (start a bill, propose a purchase) whose wording is already auditor-checked.

The final free-text answer is audited against the numbers in this turn's tool results plus the
conversation; one rewrite is allowed, then the caller's fallback runs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from contracts.models import Reply

from .. import fixtures, registry, trace
from .auditor import numbers_in

MAX_STEPS = 4
MAX_CALLS_PER_STEP = 4
# "I'll check" / "let me set that up" without a tool call: the model announced work it didn't do.
PROMISE = re.compile(r"\b(?:i'?ll|i will|let me|gonna|going to)\s+(?:go\s+)?(?:check|set|post|run|propose|"
                     r"look|start|pull|get|crunch|ask|figure|kick)\b", re.I)


@dataclass
class ToolOutput:
    data: dict
    replies: list[Reply] | None = None  # set by action tools: ends the turn with these replies


@dataclass
class AgentTool:
    name: str
    description: str
    params: dict  # JSON-schema "properties"
    run: Callable[[dict], ToolOutput]
    required: tuple[str, ...] = ()

    def spec(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": {"type": "object", "properties": self.params, "required": list(self.required)}}}


@dataclass
class Outcome:
    text: str = ""
    replies: list[Reply] | None = None
    allowed: set[float] = field(default_factory=set)
    tools_used: list[str] = field(default_factory=list)  # calls that ran
    tools_tried: list[str] = field(default_factory=list)  # every call the model made, failed ones too
    messages: list[dict] = field(default_factory=list)


def _numbers(value: object) -> set[float]:
    """Every number in a tool result, including ones inside strings (dates are skipped)."""
    if isinstance(value, bool):
        return set()
    if isinstance(value, (int, float)):
        return {round(abs(float(value)), 2)}  # -800 (money out) is quoted as $800
    if isinstance(value, str):
        return set(numbers_in(value))
    if isinstance(value, dict):
        return set().union(*(_numbers(v) for v in value.values())) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*(_numbers(v) for v in value)) if value else set()
    return set()


def run(agent: str, system: str, user: str, tools: list[AgentTool]) -> Outcome:
    llm = registry.get("llm")
    by_name = {t.name: t for t in tools}
    specs = [t.spec() for t in tools]
    out = Outcome(allowed=set(numbers_in(user)))
    out.messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    nudged = False
    for _ in range(MAX_STEPS):
        result = llm.chat(out.messages, specs)
        if not result.tool_calls:
            text = result.text.strip()
            if not nudged and (PROMISE.search(text) or any(t.name in text for t in tools)):
                nudged = True
                trace.log(agent, "nudged", f"announced instead of calling a tool: {text[:60]}")
                out.messages += [{"role": "assistant", "content": text},
                                 {"role": "user", "content": "Don't announce it: call the tool now, then answer."}]
                continue
            out.text = text
            return out
        results = []
        for call in result.tool_calls[:MAX_CALLS_PER_STEP]:
            tool = by_name.get(call.name)
            trace.log(agent, "tool", f"{call.name}({json.dumps(call.args)[:80]})")
            out.tools_tried.append(call.name)
            if tool is None:
                results.append({"tool": call.name, "error": "unknown tool"})
                continue
            try:
                done = tool.run(call.args)
            except (ValueError, KeyError, TypeError) as e:  # bad args from the model: tell it, let it retry
                trace.log(agent, "tool_error", f"{call.name}: {e}")
                results.append({"tool": call.name, "error": str(e)})
                continue
            out.tools_used.append(call.name)
            if done.replies is not None:
                out.replies = done.replies
                return out
            out.allowed |= _numbers(done.data)
            results.append({"tool": call.name, "args": call.args, "result": done.data})
        names = ", ".join(c.name for c in result.tool_calls)
        out.messages += [
            {"role": "assistant", "content": result.text or f"(calling {names})"},
            {"role": "user", "content": "TOOL RESULTS:\n" + json.dumps(results, default=str)
             + "\nAnswer the latest message now, or call another tool if you still need something."},
        ]
    trace.log(agent, "tool_limit", f"stopped after {MAX_STEPS} tool rounds")
    return out


def silent(out: Outcome) -> bool:
    """True when the LLM used no tool and gave no real answer: stub mode, or Grok down and the
    adapter fell back to StubLLM's hello script. Callers then use their keyword/scripted path."""
    return out.replies is None and not out.tools_tried and out.text in ("", fixtures.expected().scripts.hello_group)


def checked(agent: str, out: Outcome, audience: str, extra_allowed: set[float] = frozenset()) -> str | None:
    """Audit the loop's final text; ask the LLM for one rewrite if blocked. None = use the fallback."""
    if not out.text:
        return None
    auditor, allowed = registry.get("auditor"), out.allowed | set(extra_allowed)
    text = out.text
    for attempt in range(2):
        res = auditor.check(text, allowed, audience)
        if res.ok:
            trace.log(agent, "replied", f"to {audience}: {text[:80]}")
            return text
        if attempt == 1:
            break
        messages = out.messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": "The auditor blocked that: " + "; ".join(res.reasons)
             + ". Rewrite it using only numbers from the tool results or the conversation."}]
        text = registry.get("llm").chat(messages).text.strip()
        if not text:
            break
    trace.log("auditor", "fallback", f"{agent} -> {audience}: loop answer blocked")
    return None
