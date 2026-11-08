"""M11 route tests: every response matches contracts/models.py, errors are JSON, CORS, N9,
payday crediting on /demo/advance, and the M16 http outbox. Runs under both TEST_PROFILEs."""
from __future__ import annotations

import ast
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from contracts.models import (
    AdvanceOut, BankView, ChatOut, ErrorOut, HealthOut, HouseState, Leg, OkOut, Owe, SendIn,
)

from app import config, registry, views
from app.main import app

SEED = {"alex": 4200, "sam": 2600, "jordan": 310}
DASHBOARD = "http://localhost:3000"


@pytest.fixture
def client() -> TestClient:
    c = TestClient(app, raise_server_exceptions=False)
    assert c.post("/demo/reset").status_code == 200
    return c


def keys(model: type[BaseModel]) -> set[str]:
    return {f.alias or name for name, f in model.model_fields.items()}


def shaped(model: type[BaseModel], body: dict) -> BaseModel:
    """Validate against the contract model and require exactly its JSON keys."""
    assert set(body) == keys(model), (model.__name__, sorted(body))
    return model.model_validate(body)


def chat(c: TestClient, who: str, text: str, chat_type: str = "group"):
    return c.post("/chat", json={"chat_type": chat_type, "sender_handle": f"sim:{who}", "text": text,
                                 "message_id": f"{who}-{text}-{time.monotonic_ns()}",
                                 "ts": "2026-11-28T09:00:00Z"})


def approve_rent(c: TestClient) -> None:
    assert c.post("/demo/trigger", json={"event": "rent_due"}).status_code == 200
    for who in SEED:
        assert chat(c, who, "yes").status_code == 200


def assert_error(r, status: int, error: str | None = None) -> ErrorOut:
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/json")
    e = shaped(ErrorOut, r.json())
    assert e.ok is False
    if error is not None:
        assert e.error == error
    return e


# ---------- shapes ----------

def test_chat_shapes(client):
    for who, text, kind in [("alex", "hi", "group"), ("jordan", "what's my runway?", "dm")]:
        r = chat(client, who, text, kind)
        assert r.status_code == 200
        out = shaped(ChatOut, r.json())
        assert out.replies
        for reply in r.json()["replies"]:
            assert set(reply) == {"target", "text"}
    r = client.post("/chat", json={"chat_type": "dm", "sender_handle": "+15550000000", "text": "hi",
                                   "message_id": "u1", "ts": "2026-11-28T09:00:00Z"})
    assert shaped(ChatOut, r.json()).replies[0].text == "I don't know you yet."


def test_state_shape(client):
    approve_rent(client)
    body = client.get("/state").json()
    st = shaped(HouseState, body)
    assert st.today == "2026-11-28" and len(st.roommates) == 3
    for owe in body["owes"]:
        assert set(owe) == keys(Owe)
    for p in body["proposals"]:
        for leg in p["legs"]:
            assert "from" in leg and "from_" not in leg and set(leg) <= keys(Leg)
    assert len(body["trace"]) <= 50


@pytest.mark.parametrize("rid", sorted(SEED))
def test_bank_shape(client, rid):
    v = shaped(BankView, client.get(f"/bank/{rid}").json())
    assert v.roommate_id == rid and v.balance == SEED[rid]


@pytest.mark.parametrize("event", ["rent_due", "electric_bill", "watch"])
def test_trigger_shape(client, event):
    r = client.post("/demo/trigger", json={"event": event})
    assert r.status_code == 200 and shaped(OkOut, r.json()).ok


def test_reset_and_advance_shapes(client):
    assert shaped(OkOut, client.post("/demo/reset").json()).ok
    approve_rent(client)
    out = shaped(AdvanceOut, client.post("/demo/advance", json={"to": "2026-12-16"}).json())
    assert out.ok and [leg.from_ for leg in out.executed] == ["jordan"]
    for leg in client.post("/demo/advance", json={"to": "2026-12-17"}).json()["executed"]:
        assert "from" in leg


def test_health_shape(client):
    h = shaped(HealthOut, client.get("/health").json())
    assert h.ok and set(h.modes) == set(registry.ENV)
    assert h.llm_mode == h.modes["llm"] and h.nessie_mode == h.modes["nessie"]


# ---------- demo control ----------

def test_reset_restores_seed_quickly(client):  # N9
    approve_rent(client)
    client.post("/demo/advance", json={"to": "2026-12-16"})
    t0 = time.perf_counter()
    assert client.post("/demo/reset").json() == {"ok": True}
    assert time.perf_counter() - t0 < 5
    st = client.get("/state").json()
    assert st["today"] == "2026-11-28" and st["proposals"] == [] and st["owes"] == []
    for rid, bal in SEED.items():
        assert client.get(f"/bank/{rid}").json()["balance"] == bal


def test_failed_reset_keeps_previous_state(client, monkeypatch):
    """If Nessie can't be seeded, /demo/reset is a 502 and nothing is half-reset."""
    from contracts.interfaces import NessieError
    approve_rent(client)
    client.post("/demo/advance", json={"to": "2026-12-02"})
    before_state = client.get("/state").json()
    before_bank = {rid: client.get(f"/bank/{rid}").json() for rid in SEED}

    nessie_cls = type(registry.get("nessie"))
    real_seed = nessie_cls.seed

    def down(self, scenario):
        raise NessieError("Nessie POST /customers network error")
    monkeypatch.setattr(nessie_cls, "seed", down)
    assert_error(client.post("/demo/reset"), 502, "NessieError")

    after = client.get("/state").json()
    assert (after["today"], after["proposals"], after["owes"]) == (
        before_state["today"], before_state["proposals"], before_state["owes"])
    for rid in SEED:
        r = client.get(f"/bank/{rid}")
        assert r.status_code == 200 and r.json() == before_bank[rid]

    monkeypatch.setattr(nessie_cls, "seed", real_seed)  # Nessie back up: reset works again
    assert client.post("/demo/reset").json() == {"ok": True}
    assert client.get("/state").json()["today"] == "2026-11-28"


def test_advance_credits_crossed_paydays(client):
    r = client.post("/demo/advance", json={"to": "2026-12-16"})
    assert r.status_code == 200 and r.json()["executed"] == []
    pay = {"alex": 5800, "sam": 1900, "jordan": 1350}  # 12-01, 12-05, 12-15
    for rid, amount in pay.items():
        bank = client.get(f"/bank/{rid}").json()
        assert bank["balance"] == SEED[rid] + amount
        deposits = [t for t in bank["transactions"] if t["description"] == "Payroll deposit"]
        assert [t["amount"] for t in deposits][:1] == [amount]
    assert client.get("/state").json()["today"] == "2026-12-16"


# ---------- errors are always JSON ----------

def test_unknown_roommate_404(client):
    assert_error(client.get("/bank/nobody"), 404, "http_404")


def test_unknown_route_404(client):
    assert_error(client.get("/nope"), 404, "http_404")


@pytest.mark.parametrize("to", ["not-a-date", "2026-11-01"])
def test_bad_advance_400(client, to):
    assert_error(client.post("/demo/advance", json={"to": to}), 400, "http_400")


@pytest.mark.parametrize("path,body", [
    ("/demo/trigger", {"event": "fireworks"}),
    ("/chat", {"chat_type": "group", "text": "hi"}),
    ("/demo/advance", {}),
])
def test_bad_body_422(client, path, body):
    e = assert_error(client.post(path, json=body), 422, "validation")
    assert isinstance(e.detail, list) and e.detail


def test_module_crash_is_json_500(client, monkeypatch):
    def boom():
        raise RuntimeError("store exploded")
    monkeypatch.setattr(views, "house_state", boom)
    r = client.get("/state", headers={"Origin": DASHBOARD})
    e = assert_error(r, 500, "RuntimeError")
    assert e.detail == "store exploded"
    assert r.headers["access-control-allow-origin"] == DASHBOARD  # browser can read the error


def test_unbuilt_mode_is_json_501(client, use):
    use(store="tiger")
    assert_error(client.get("/state"), 501, "NotImplementedError")


def test_bad_mode_flag_is_json_500(client, use):
    use(nessie="bogus")
    e = assert_error(client.get("/health"), 500, "ValueError")
    assert "NESSIE_MODE" in e.detail


def test_gateway_down_is_json_502(client, use, monkeypatch):
    monkeypatch.setenv("GATEWAY_URL", "http://127.0.0.1:9")
    use(outbox="http")
    assert_error(client.post("/demo/trigger", json={"event": "rent_due"}), 502, "ConnectionError")


# ---------- CORS ----------

def _preflight(c: TestClient, origin: str):
    return c.options("/state", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:8081", "http://localhost:19006"])
def test_cors_allows_dev_origins(client, origin):
    r = _preflight(client, origin)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin
    assert client.get("/health", headers={"Origin": origin}).headers["access-control-allow-origin"] == origin


def test_cors_rejects_other_origins(client):
    r = _preflight(client, "http://evil.example")
    assert "access-control-allow-origin" not in r.headers
    assert "access-control-allow-origin" not in client.get("/health", headers={"Origin": "http://evil.example"}).headers


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://house.example/ ,http://localhost:3000,")
    monkeypatch.setenv("EXPO_TUNNEL_URL", "https://abc-anonymous-8081.exp.direct/")
    origins = config.cors_origins()
    assert origins[:4] == list(config.DEV_ORIGINS)
    assert origins[4:] == ["https://house.example", "https://abc-anonymous-8081.exp.direct"]


# ---------- M16 http outbox ----------

@pytest.fixture
def gateway():
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            assert self.path == "/send"
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", received
    server.shutdown()
    server.server_close()


def test_http_outbox_posts_send_bodies(client, use, monkeypatch, gateway):
    url, received = gateway
    monkeypatch.setenv("GATEWAY_URL", url)
    use(outbox="http")
    assert client.post("/demo/trigger", json={"event": "rent_due"}).json() == {"ok": True}
    assert received, "trigger sent nothing to the gateway"
    sends = [SendIn.model_validate(b) for b in received]
    assert sends[0].target.type == "group" and "$800" in sends[0].text
    assert any(s.target.type == "dm" and s.target.roommate_id == "jordan" for s in sends)
    for who in SEED:  # treasurer confirmation also goes through the outbox
        chat(client, who, "yes")
    assert len(received) > len(sends)


# ---------- routes reach modules only through the registry ----------

API_FILES = ["main.py", "chat.py", "views.py", "demo.py"]
ALLOWED = {"registry", "trace", "fixtures", "config", "fmt", "chat", "views", "demo"}


@pytest.mark.parametrize("name", API_FILES)
def test_api_imports_only_registry(name):
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app" / name).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level == 1:  # from . import x / from .x import y
                mods = [node.module] if node.module else [a.name for a in node.names]
            elif node.module and node.module.startswith("app"):
                mods = [node.module.split(".", 1)[1] if "." in node.module else node.module]
            else:
                continue
            for m in mods:
                assert m.split(".")[0] in ALLOWED, f"{name} imports app.{m} directly; use the registry"
        elif isinstance(node, ast.Import):
            for a in node.names:
                assert not a.name.startswith("app."), f"{name} imports {a.name} directly"


def test_live_nessie_is_seeded_on_startup(monkeypatch):
    """A fresh live-Nessie brain must not 500 on /state: startup reseeds (like /demo/reset)."""
    from fastapi.testclient import TestClient

    from app import demo, main

    calls = []
    monkeypatch.setattr(main.registry, "mode", lambda name: "live" if name == "nessie" else "stub")
    monkeypatch.setattr(demo, "reset", lambda: calls.append("reset"))
    with TestClient(main.app):
        pass
    assert calls == ["reset"]
