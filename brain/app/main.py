"""Brain HTTP API (routes only). Everything goes through the registry."""
from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from contracts.models import AdvanceIn, AdvanceOut, BankView, ChatIn, ChatOut, HouseState, OkOut, TriggerIn

from . import chat, demo, registry, views
from .fixtures import ROOT

load_dotenv(ROOT / ".env")  # never overrides variables already set in the environment

app = FastAPI(title="House Rules brain")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.post("/chat", response_model=ChatOut)
def post_chat(msg: ChatIn) -> ChatOut:
    return chat.handle(msg)


@app.get("/state", response_model=HouseState)
def get_state() -> HouseState:
    return views.house_state()


@app.get("/bank/{roommate_id}", response_model=BankView)
def get_bank(roommate_id: str) -> BankView:
    try:
        return views.bank_view(roommate_id)
    except KeyError as e:
        raise HTTPException(404, f"unknown roommate {roommate_id}") from e


@app.post("/demo/reset", response_model=OkOut)
def demo_reset() -> OkOut:
    demo.reset()
    return OkOut(ok=True)


@app.post("/demo/trigger", response_model=OkOut)
def demo_trigger(body: TriggerIn) -> OkOut:
    demo.trigger(body.event)
    return OkOut(ok=True)


@app.post("/demo/advance", response_model=AdvanceOut)
def demo_advance(body: AdvanceIn) -> AdvanceOut:
    try:
        executed = demo.advance(body.to)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return AdvanceOut(ok=True, executed=executed)


@app.get("/health")
def health() -> dict:
    m = registry.modes()
    return {"ok": True, "llm_mode": m["llm"], "nessie_mode": m["nessie"], "modes": m}
