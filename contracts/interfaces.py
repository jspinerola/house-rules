"""One Protocol per brain module (frozen). Modules reach each other only via
brain/app/registry.py, which hands out a stub or real implementation per <MODULE>_MODE.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from .models import (
    Affordability, Ask, AuditResult, Bill, BankTxn, CoverAnswer, DemoEvent, HouseRule, Indicator,
    Leg, LLMResult, PaydayPlan, Proposal, Release, Reply, Roommate, Scenario, SplitResult,
    TraceEvent, Transaction, Verdict,
)


class NessieError(Exception):
    """Raised by a Nessie client when a money movement fails; the Treasurer reports it."""


@runtime_checkable
class Store(Protocol):  # M1, DB_MODE
    def get_roommate(self, rid: str) -> Roommate: ...
    def by_handle(self, handle: str) -> Roommate | None: ...
    def roommates(self) -> list[Roommate]: ...
    def transactions(self, rid: str, since: str | None = None) -> list[Transaction]: ...
    def add_transaction(self, txn: Transaction) -> None: ...
    def bill(self, bill_type: str) -> Bill: ...
    def house_rule(self, bill_type: str) -> HouseRule | None: ...
    def save_proposal(self, p: Proposal) -> None: ...
    def get_proposal(self, pid: str) -> Proposal: ...
    def proposals(self) -> list[Proposal]: ...  # oldest first
    def pending_for(self, rid: str) -> list[Proposal]: ...  # rid's approval still pending, oldest first
    def add_trace(self, e: TraceEvent) -> None: ...
    def recent_trace(self, n: int = 50) -> list[TraceEvent]: ...  # newest first
    def today(self) -> str: ...
    def set_today(self, d: str) -> None: ...
    def reset(self) -> None: ...  # reload scenario, clock -> scenario.today


@runtime_checkable
class Indicators(Protocol):  # M2, INDICATORS_MODE
    def compute(self, rid: str) -> dict[str, Indicator]: ...


@runtime_checkable
class Tools(Protocol):  # M3, TOOLS_MODE (pure code, no LLM)
    def split_bill(self, bill_type: str, amount: float) -> SplitResult: ...
    def can_cover(self, rid: str, amount: float, date: str) -> CoverAnswer: ...
    def payday_plan(self, rid: str, amount: float) -> PaydayPlan: ...
    def group_affordability(
        self, item: str, price: float, months_options: tuple[int, ...] = (1, 3)
    ) -> Affordability: ...
    def next_payday(self, rid: str, after: str) -> str | None: ...  # first payday strictly after `after`


@runtime_checkable
class Proposals(Protocol):  # M4, PROPOSALS_MODE
    def parse(self, text: str) -> Verdict | None: ...
    def create(self, flow: str, title: str, legs: list[Leg], approvers: list[str]) -> Proposal: ...
    def record_reply(self, rid: str, text: str) -> Proposal | None: ...
    def get(self, pid: str) -> Proposal: ...
    def pending(self) -> list[Proposal]: ...


@runtime_checkable
class Auditor(Protocol):  # M5, AUDITOR_MODE
    def check(self, text: str, allowed_numbers: set[float], audience: str) -> AuditResult: ...
    # audience: "group" or a roommate_id


@runtime_checkable
class LLM(Protocol):  # M6, LLM_MODE
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResult: ...


@runtime_checkable
class Personal(Protocol):  # M7, PERSONAL_MODE
    def ask(self, rid: str, question: Ask) -> Release: ...
    def dm(self, rid: str, text: str) -> list[Reply]: ...
    def explain(self, rid: str, proposal: Proposal) -> list[Reply]: ...  # private DM about a proposal


@runtime_checkable
class House(Protocol):  # M8, HOUSE_MODE
    def on_message(self, sender_rid: str, text: str) -> list[Reply]: ...
    def on_event(self, event: DemoEvent) -> list[Reply]: ...


@runtime_checkable
class Nessie(Protocol):  # M9, NESSIE_MODE (only the Treasurer and demo seeding write)
    def seed(self, scenario: Scenario) -> None: ...
    def balance(self, rid: str) -> float: ...
    def transactions(self, rid: str) -> list[BankTxn]: ...  # newest first
    def transfer(self, from_rid: str, to_rid: str, amount: float, description: str) -> str: ...
    def pay_bill(self, rid: str, payee: str, amount: float, date: str) -> str: ...
    def purchase(self, rid: str, merchant: str, amount: float, description: str) -> str: ...
    def deposit(self, rid: str, amount: float, description: str) -> str: ...  # demo paydays


@runtime_checkable
class Treasurer(Protocol):  # M10, TREASURER_MODE
    def execute(self, pid: str) -> list[Leg]: ...  # raises unless approved
    def run_due(self, today: str) -> list[Leg]: ...


@runtime_checkable
class Outbox(Protocol):  # proactive messages to the gateway, OUTBOX_MODE
    def send(self, reply: Reply) -> None: ...


ModuleName = Literal[
    "store", "indicators", "tools", "proposals", "auditor", "llm",
    "personal", "house", "nessie", "treasurer", "outbox",
]

PROTOCOLS: dict[str, type] = {
    "store": Store, "indicators": Indicators, "tools": Tools, "proposals": Proposals,
    "auditor": Auditor, "llm": LLM, "personal": Personal, "house": House,
    "nessie": Nessie, "treasurer": Treasurer, "outbox": Outbox,
}
