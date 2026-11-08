"""LLM providers: offline mock, local open-weight (Ollama), commercial (OpenAI-compatible)."""
import json
import os
import re
import urllib.request


def _post(url, body, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


class MockLLM:
    """Deterministic stand-in so every exercise runs with no model or API key."""
    name = "mock"

    def chat(self, messages):
        system, user = messages[0]["content"], messages[-1]["content"]
        if "ROLE:ROUTER" in system:
            q = user.lower()
            if "car" in q or "buy" in q or "what if" in q:
                nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", q)]
                args = {}
                if len(nums) >= 2:
                    args = {"price": nums[0], "down": nums[1]}
                return json.dumps({"tool": "simulate_car_purchase", "args": args})
            if "forecast" in q or "future" in q:
                return json.dumps({"tool": "forecast_balances", "args": {}})
            if "account" in q:
                return json.dumps({"tool": "get_accounts", "args": {}})
            return json.dumps({"tool": "calculate_health_metrics", "args": {}})
        return "Based on the verified figures: " + user.split("EVIDENCE:", 1)[-1].strip()[:600]


class OllamaLLM:
    """Open-weight model running locally (https://ollama.com). e.g. llama3.2, qwen2.5."""

    def __init__(self, model="llama3.2", host="http://localhost:11434"):
        self.name, self.model, self.host = f"ollama:{model}", model, host

    def chat(self, messages):
        r = _post(f"{self.host}/api/chat", {"model": self.model, "messages": messages, "stream": False})
        return r["message"]["content"]


class OpenAILLM:
    """Commercial API via OpenAI-compatible chat completions. Needs OPENAI_API_KEY."""

    def __init__(self, model="gpt-4o-mini", base_url="https://api.openai.com/v1"):
        self.name, self.model, self.base_url = f"openai:{model}", model, base_url

    def chat(self, messages):
        key = os.environ["OPENAI_API_KEY"]
        r = _post(f"{self.base_url}/chat/completions", {"model": self.model, "messages": messages},
                  {"Authorization": "Bearer " + key})
        return r["choices"][0]["message"]["content"]


def get_llm(spec="mock"):
    """spec: 'mock', 'ollama[:model]', or 'openai[:model]'."""
    kind, _, model = spec.partition(":")
    if kind == "mock":
        return MockLLM()
    if kind == "ollama":
        return OllamaLLM(model or "llama3.2")
    if kind == "openai":
        return OpenAILLM(model or "gpt-4o-mini")
    raise ValueError(f"unknown LLM spec: {spec}")


class GrokLLM:
    """House Rules addition: xAI Grok via the OpenAI SDK, with tool calling.

    Returns a plain assistant message dict ({"content", "tool_calls"}). Needs XAI_API_KEY.
    """

    def __init__(self, model=None, base_url="https://api.x.ai/v1", timeout=8):
        from openai import OpenAI

        self.model = model or os.environ.get("GROK_MODEL", "")
        if not self.model:
            raise ValueError("GROK_MODEL is not set")
        key = os.environ.get("XAI_API_KEY")
        if not key:
            raise ValueError("XAI_API_KEY is not set")
        self.name, self.base_url, self.timeout = f"grok:{self.model}", base_url, timeout
        self._client = OpenAI(api_key=key, base_url=base_url, timeout=timeout)

    def chat(self, messages, tools=None):
        kwargs = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        msg = self._client.chat.completions.create(**kwargs).choices[0].message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [{
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            } for tc in msg.tool_calls]
        return {"content": msg.content, "tool_calls": tool_calls}
