"""Brain HTTP API (routes only). Everything goes through the registry."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from contracts.interfaces import NessieError
from contracts.models import (
    AdvanceIn, AdvanceOut, BankView, ChatIn, ChatOut, ErrorOut, HealthOut, HouseState, OkOut, TriggerIn,
)

from . import chat, config, demo, registry, views
from .fixtures import ROOT

load_dotenv(ROOT / ".env")  # never overrides variables already set in the environment

log = logging.getLogger("brain")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The live Nessie client keeps account ids and the cents ledger in memory, so a fresh brain
    # can't answer anything until Nessie is seeded. Reseed on startup so the demo is usable
    # right away (same as POST /demo/reset: store and Nessie start from the scenario together).
    if registry.mode("nessie") == "live":
        log.warning("NESSIE_MODE=live: seeding Nessie and resetting the demo on startup")
        demo.reset()
    yield


app = FastAPI(title="House Rules brain", lifespan=lifespan)

# Unhandled module errors -> HTTP status. Anything else is a 500.
ERROR_STATUS: list[tuple[type[BaseException], int]] = [
    (NessieError, 502),          # bank call failed
    (ConnectionError, 502),      # gateway (outbox) unreachable
    (NotImplementedError, 501),  # a <MODULE>_MODE that isn't built yet
]


def _error(status: int, error: str, detail: str | list) -> JSONResponse:
    return JSONResponse(ErrorOut(error=error, detail=detail).model_dump(), status_code=status)


# Registered before CORS so CORS wraps it and error responses keep their CORS headers.
@app.middleware("http")
async def json_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:  # last line of defence: never let Starlette send its plain-text 500
        status = next((s for cls, s in ERROR_STATUS if isinstance(e, cls)), 500)
        log.exception("%s %s failed with %d", request.method, request.url.path, status)
        return _error(status, type(e).__name__, str(e))


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, e: StarletteHTTPException) -> JSONResponse:
    return _error(e.status_code, f"http_{e.status_code}", str(e.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, e: RequestValidationError) -> JSONResponse:
    return _error(422, "validation", jsonable_encoder(e.errors()))


app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


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


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    m = registry.modes()
    return HealthOut(ok=True, llm_mode=m["llm"], nessie_mode=m["nessie"], modes=m)
