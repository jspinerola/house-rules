"""Acceptance smoke (AGENTS.md): rent day, payday fronting, couch. Runs on all stubs and on
all real modules except Nessie, LLM and Outbox."""
from __future__ import annotations

import itertools
import re

import pytest
from fastapi.testclient import TestClient

from app import registry
from app.main import app
from tests.conftest import ALL_REAL, ALL_STUB

PRIVATE = ["310", "1,350", "1350", "2,600", "2600", "4,200", "4200", "5,800", "5800", "1,900", "1900"]
_ids = itertools.count()

PROFILES = [
    pytest.param(ALL_STUB, id="stub"),
    pytest.param(ALL_REAL, id="real", marks=pytest.mark.skipif(
        not all(registry.available(n, "real") for n in
                ("store", "indicators", "tools", "proposals", "auditor", "personal", "house", "treasurer")),
        reason="real modules not all implemented yet")),
]


@pytest.fixture(params=PROFILES)
def client(request, use):
    use(profile=request.param)
    c = TestClient(app)
    assert c.post("/demo/reset").json() == {"ok": True}
    return c


def say(c: TestClient, who: str, text: str, chat_type: str = "group") -> list[dict]:
    body = {"chat_type": chat_type, "sender_handle": f"sim:{who}", "text": text,
            "message_id": f"m{next(_ids)}", "ts": "2026-11-28T09:00:00Z"}
    r = c.post("/chat", json=body)
    assert r.status_code == 200, r.text
    return r.json()["replies"]


def outbox() -> list[dict]:
    return [r.model_dump(by_alias=True) for r in registry.get("outbox").sent]


def assert_no_private_numbers_in_group(replies: list[dict]) -> None:
    for r in replies:
        if r["target"]["type"] == "group":
            for figure in PRIVATE:
                assert not re.search(rf"(?<![\d,.]){re.escape(figure)}(?![\d,])", r["text"]), (figure, r["text"])


def rent_day(c: TestClient) -> dict:
    assert c.post("/demo/trigger", json={"event": "rent_due"}).json() == {"ok": True}
    sent = outbox()
    group = [r for r in sent if r["target"]["type"] == "group"]
    dms = [r for r in sent if r["target"] == {"type": "dm", "roommate_id": "jordan"}]
    assert group and "$800" in group[0]["text"] and "$2,400" in group[0]["text"]
    assert dms and "Alex" in dms[0]["text"]  # Jordan hears about fronting privately
    [p] = c.get("/state").json()["proposals"]
    assert p["flow"] == "rent" and p["status"] == "pending"
    return p


def test_health_reports_modes(client):
    h = client.get("/health").json()
    assert h["ok"] and set(h["modes"]) == set(registry.ENV)


def test_rent_day(client):
    p = rent_day(client)
    trace = client.get("/state").json()["trace"]
    assert any(e["agent"] == "personal:jordan" and e["event"] == "answered" and "no" in e["detail"]
               for e in trace)

    for who in ("alex", "sam", "jordan"):
        assert say(client, who, "yes")
    st = client.get("/state").json()
    [p] = st["proposals"]
    assert p["status"] == "executed"

    bank = client.get("/bank/alex").json()
    descs = [(t["description"], t["amount"]) for t in bank["transactions"][:5]]
    assert any("Sam" in d and a == 800 for d, a in descs), descs
    assert any("Maple Court Apartments" in d and a == -2400 for d, a in descs), descs
    assert bank["balance"] == 2600
    assert bank["scheduled"] == [{"date": "2026-12-16", "description": "From Jordan", "amount": 800}]
    assert st["owes"] == [{"from": "jordan", "to": "alex", "amount": 800, "due": "2026-12-16"}]
    assert_no_private_numbers_in_group(outbox())


def test_payday_fronting(client):
    rent_day(client)
    for who in ("alex", "sam", "jordan"):
        say(client, who, "yes")

    r = client.post("/demo/advance", json={"to": "2026-12-15"})
    assert r.status_code == 200 and r.json()["executed"] == []
    r = client.post("/demo/advance", json={"to": "2026-12-16"}).json()
    [leg] = r["executed"]
    assert (leg["from"], leg["to"], leg["amount"], leg["status"]) == ("jordan", "alex", 800, "done")

    alex = client.get("/bank/alex").json()
    assert any("Jordan" in t["description"] and t["amount"] == 800 for t in alex["transactions"][:5])
    jordan = client.get("/bank/jordan").json()
    assert jordan["balance"] == 310 + 1350 - 800
    st = client.get("/state").json()
    assert st["today"] == "2026-12-16" and st["owes"] == []
    assert client.post("/demo/advance", json={"to": "2026-12-01"}).status_code == 400
    assert_no_private_numbers_in_group(outbox())


def test_couch(client):
    replies = say(client, "alex", "can we afford a $1,200 couch?")
    assert replies[0]["target"] == {"type": "group"}
    assert "3 months" in replies[0]["text"] and "133.33" in replies[0]["text"]
    assert_no_private_numbers_in_group(replies)
    st = client.get("/state").json()
    assert len([e for e in st["trace"] if e["agent"] == "house" and e["event"] == "asked"]) == 3
    [p] = st["proposals"]
    assert p["flow"] == "purchase"

    for who in ("alex", "sam", "jordan"):
        say(client, who, "yes")
    [p] = client.get("/state").json()["proposals"]
    assert p["status"] == "executed"
    alex = client.get("/bank/alex").json()
    assert any("Couch Co." in t["description"] and t["amount"] == -1200 for t in alex["transactions"][:5])
    assert len(alex["scheduled"]) == 4  # two more months from Sam and Jordan
    assert client.get("/bank/jordan").json()["balance"] == 176.67


def test_unknown_handle(client):
    r = client.post("/chat", json={"chat_type": "dm", "sender_handle": "+15550009999", "text": "hi",
                                   "message_id": "x", "ts": "2026-11-28T09:00:00Z"}).json()
    assert r["replies"][0]["text"] == "I don't know you yet."
