"""Integration checkpoint I5a (REQUIREMENTS I5 minus Photon): I4 stack + LLM_MODE=grok + OUTBOX_MODE=http.

Opt-in: RUN_LIVE_GROK=1 with XAI_API_KEY and NESSIE_API_KEY. Runs rent day, couch and the
electric bill through /chat with live Grok wording every reply, then checks: no llm_fallback,
no auditor fallback, no private numbers in the group, and /bank matches fixtures/expected.json.
A local /send listener stands in for the sim gateway so the http outbox is exercised for real.
"""
from __future__ import annotations

import itertools
import json
import os
import statistics
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import fixtures, registry
from app.main import app
from tests.conftest import I4
from tests.test_e2e import assert_no_private_numbers_in_group

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

I5A = {**I4, "LLM_MODE": "grok", "OUTBOX_MODE": "http"}
_ids = itertools.count()


def _run_live() -> bool:
    return (os.environ.get("RUN_LIVE_GROK") or "").strip() == "1" and all(
        (os.environ.get(k) or "").strip() for k in ("XAI_API_KEY", "NESSIE_API_KEY"))


pytestmark = pytest.mark.skipif(
    not _run_live(), reason="set RUN_LIVE_GROK=1 with XAI_API_KEY and NESSIE_API_KEY to run I5a")


@pytest.fixture
def gateway(monkeypatch):
    """Minimal sim-gateway /send that records every proactive Reply body."""
    sent: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("content-length", 0)))
            if self.path != "/send":
                self.send_response(404), self.end_headers()
                return
            sent.append(json.loads(body))
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *_):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("GATEWAY_URL", f"http://127.0.0.1:{srv.server_address[1]}")
    yield sent
    srv.shutdown()


def _expected_balances() -> dict[str, float]:
    """Seed checking + every expected.json leg due by today (rent, couch) + the electric split."""
    scen, exp = fixtures.scenario(), json.loads(
        (Path(__file__).resolve().parents[2] / "fixtures" / "expected.json").read_text())
    bal = {r.id: next(a.balance for a in r.accounts if a.type == "checking") for r in scen.roommates}
    elec = next(b for b in scen.bills if b.type == "electric")
    shares = next(s for s in exp["split_bill"] if s["bill_type"] == "electric")["expect"]["shares"]
    legs = exp["proposals"]["rent"]["legs"] + exp["proposals"]["couch"]["legs"]
    legs += [{"from": r, "to": elec.payer, "amount": a, "date": scen.today} for r, a in shares.items()
             if r != elec.payer]
    legs.append({"from": elec.payer, "to": None, "amount": elec.amount, "date": scen.today})
    for leg in legs:
        if leg["date"] <= scen.today:
            bal[leg["from"]] -= leg["amount"]
            if leg.get("to"):
                bal[leg["to"]] += leg["amount"]
    return {k: round(v, 2) for k, v in bal.items()}


def test_I5a_live_grok_full_flow(use, gateway):
    use(profile=I5A)
    c = TestClient(app)
    assert c.post("/demo/reset").json() == {"ok": True}
    h = c.get("/health").json()
    assert h["llm_mode"] == "grok" and h["nessie_mode"] == "live" and h["modes"]["outbox"] == "http"

    # Time every Grok round trip on the live instance.
    llm = registry.get("llm")
    latencies: list[float] = []
    real_chat = llm.chat

    def timed(messages, tools=None):
        t = time.perf_counter()
        try:
            return real_chat(messages, tools)
        finally:
            latencies.append(time.perf_counter() - t)
    llm.chat = timed

    replies: list[dict] = []

    def say(who: str, text: str) -> None:
        r = c.post("/chat", json={"chat_type": "group", "sender_handle": f"sim:{who}", "text": text,
                                  "message_id": f"i5a-{next(_ids)}", "ts": "2026-11-28T09:00:00Z"})
        assert r.status_code == 200, r.text
        replies.extend(r.json()["replies"])

    def approve_latest(flow: str) -> None:
        p = [x for x in c.get("/state").json()["proposals"] if x["flow"] == flow][-1]
        for who in p["required_approvers"]:
            say(who, "yes")
        p = next(x for x in c.get("/state").json()["proposals"] if x["id"] == p["id"])
        assert p["status"] == "executed", (flow, p["status"])

    assert c.post("/demo/trigger", json={"event": "rent_due"}).json() == {"ok": True}
    approve_latest("rent")
    say("alex", "can we afford a $1,200 couch?")
    approve_latest("purchase")
    assert c.post("/demo/trigger", json={"event": "electric_bill"}).json() == {"ok": True}
    approve_latest("utility")

    trace = registry.get("store").recent_trace(10_000)
    blocked = [e for e in trace if e.agent == "auditor" and e.event == "blocked"]
    for e in reversed(blocked):
        print(f"I5a auditor blocked: {e.detail}")
    if latencies:
        print(f"I5a grok calls: {len(latencies)} avg {statistics.mean(latencies):.2f}s "
              f"max {max(latencies):.2f}s")

    fallbacks = [e.detail for e in trace if e.event == "llm_fallback"]
    assert not fallbacks, f"llm_fallback: {fallbacks}"
    auditor_fallbacks = [e.detail for e in trace if e.agent == "auditor" and e.event == "fallback"]
    assert not auditor_fallbacks, f"auditor fallback (Grok text never passed): {auditor_fallbacks}"
    worded = [e for e in trace if e.event == "replied"]
    assert worded and len(latencies) >= len(worded)

    assert gateway, "http outbox never reached /send"
    assert_no_private_numbers_in_group(replies + gateway)

    want = _expected_balances()
    got = {rid: c.get(f"/bank/{rid}").json()["balance"] for rid in want}
    assert got == pytest.approx(want, abs=0.005)
