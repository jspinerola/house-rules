"""Shared JSON shapes (frozen). Mirrors SPEC.md "JSON shapes" and contracts/types.ts.

Change only in a contracts-only PR with a heads-up to the team.
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

Level = Literal["ok", "tight", "no"]
IndicatorStatus = Literal["good", "watch", "risk"]
Verdict = Literal["yes", "no"]
ApprovalState = Literal["pending", "yes", "no"]
LegType = Literal["transfer", "scheduled_transfer", "bill_payment", "purchase"]
LegStatus = Literal["pending", "done", "failed"]
Flow = Literal["rent", "front", "purchase", "utility", "rule"]
ProposalStatus = Literal["pending", "approved", "executed", "rejected", "failed"]
AgentName = Literal[
    "house", "personal:alex", "personal:sam", "personal:jordan", "treasurer", "auditor", "watcher"
]
DemoEvent = Literal["rent_due", "electric_bill", "watch"]


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ---------- gateway <-> brain ----------

class ChatIn(_Model):
    chat_type: Literal["group", "dm"]
    sender_handle: str
    text: str
    message_id: str
    ts: str


class GroupTarget(_Model):
    type: Literal["group"] = "group"


class DMTarget(_Model):
    type: Literal["dm"] = "dm"
    roommate_id: str


Target = Annotated[Union[GroupTarget, DMTarget], Field(discriminator="type")]


class Reply(_Model):
    target: Target
    text: str


class ChatOut(_Model):
    replies: list[Reply] = []


# ---------- money movement ----------

class Leg(_Model):
    type: LegType
    from_: str = Field(alias="from")
    to: str | None = None
    payee: str | None = None
    amount: float
    date: str
    status: LegStatus = "pending"
    nessie_id: str | None = None


class Proposal(_Model):
    id: str
    flow: Flow
    title: str
    legs: list[Leg]
    required_approvers: list[str]
    approvals: dict[str, ApprovalState]
    status: ProposalStatus = "pending"
    rule: HouseRule | None = None  # flow "rule": the rule being voted on; split {} means remove it


class TraceEvent(_Model):
    ts: str
    agent: AgentName
    event: str
    detail: str


# ---------- read views ----------

class RoommateStatus(_Model):
    id: str
    name: str
    balance: float
    status: Level
    next_payday: str


class Owe(_Model):
    from_: str = Field(alias="from")
    to: str
    amount: float
    due: str


class HouseState(_Model):
    today: str
    roommates: list[RoommateStatus]
    owes: list[Owe]
    proposals: list[Proposal]
    trace: list[TraceEvent]  # newest first, max 50
    rules: list[HouseRule] = []  # house rules in force (seeded or set in chat)


class BankTxn(_Model):
    id: str
    date: str
    description: str
    amount: float


class ScheduledPayment(_Model):
    date: str
    description: str
    amount: float


class BankView(_Model):
    bank_name: str
    roommate_id: str
    name: str
    balance: float
    transactions: list[BankTxn]  # newest first
    scheduled: list[ScheduledPayment]
    profile: Profile | None = None  # what this roommate's personal agent knows (private)


# ---------- module results ----------

class Indicator(_Model):
    value: float
    status: IndicatorStatus
    inputs: dict


CoverReason = Literal["cushion", "savings_goal", "upcoming_bills", "runway"]


class CoverAnswer(_Model):
    level: Level
    earliest_date: str | None = None
    reason: CoverReason | None = None  # why not ok; DM-only, never copied into Release


class Preferences(_Model):
    """What a roommate told their own personal agent. Private to that roommate's DM."""
    min_buffer: float | None = None       # keep at least this much in checking
    savings_monthly: float | None = None  # reserved every month for a goal
    savings_label: str | None = None
    front_cap: float | None = None        # never front more than this for someone else
    notes: list[str] = []                 # LLM context only; never used in math


class Recurring(_Model):
    name: str
    amount: float
    next_date: str


class Profile(_Model):
    """Derived from bank history + executed legs (code, deterministic) plus stated preferences."""
    income_pattern: Literal["steady", "steady_plus_side", "irregular"]
    regular_pay: float
    side_income_monthly: float
    recurring: list[Recurring]
    spend_trend_pct: float
    preferences: Preferences
    indicators: dict[str, Indicator]


class SplitResult(_Model):
    shares: dict[str, float]


class PaydayPlan(_Model):
    fronter: str
    repay_date: str


class AffordPlan(_Model):
    months: int
    per_person_monthly: float           # the even-split monthly amount
    monthly: dict[str, float] = {}      # per roommate, only when shares are uneven (purchase rule / one-off)


class Affordability(_Model):
    answers: dict[str, Level]
    plan: AffordPlan | None = None  # None when no option leaves everyone above "no"


class Ask(_Model):
    """What the house agent asks a personal agent: can you cover `amount` by `by_date`?"""
    amount: float
    by_date: str
    purpose: str


class Release(_Model):
    """The only thing a personal agent ever releases to the house agent."""
    level: Level
    earliest_date: str | None = None


class AuditResult(_Model):
    ok: bool
    reasons: list[str] = []


class ToolCall(_Model):
    name: str
    args: dict = {}


class LLMResult(_Model):
    text: str
    tool_calls: list[ToolCall] = []


# ---------- HTTP bodies ----------

class TriggerIn(_Model):
    event: DemoEvent


class AdvanceIn(_Model):
    to: str


class OkOut(_Model):
    ok: bool


class AdvanceOut(_Model):
    ok: bool
    executed: list[Leg]


class SendIn(_Model):
    target: Target
    text: str


class HealthOut(_Model):
    ok: bool
    llm_mode: str
    nessie_mode: str
    modes: dict[str, str]  # every module -> its active mode


class ErrorOut(_Model):
    """Body of every non-2xx brain response."""
    ok: Literal[False] = False
    error: str              # exception class, "http_<status>" or "validation"
    detail: str | list


# ---------- scenario fixture ----------

class PayRule(_Model):
    amount: float
    schedule: Literal["monthly", "biweekly"]
    day: int | None = None      # monthly: day of month
    anchor: str | None = None   # biweekly: any known payday


class Account(_Model):
    id: str
    type: Literal["checking", "savings", "credit_card"]
    name: str
    balance: float
    credit_limit: float | None = None


class Roommate(_Model):
    id: str
    name: str
    handle: str
    monthly_income: float
    pay: PayRule
    next_payday: str  # as of scenario.today
    accounts: list[Account]

    @property
    def checking(self) -> float:
        return sum(a.balance for a in self.accounts if a.type == "checking")


class Transaction(_Model):
    id: str
    roommate_id: str
    date: str
    description: str
    category: str
    amount: float


class Bill(_Model):
    id: str
    type: str
    amount: float
    payee: str
    payer: str
    due: str


class HouseRule(_Model):
    id: str
    bill_type: str
    split: dict[str, float]  # roommate_id -> fraction; the rest is split evenly
    source_text: str
    confirmed_by: list[str] = []


class Scenario(_Model):
    today: str
    bank_name: str
    landlord: str
    merchants: list[str]
    roommates: list[Roommate]
    transactions: list[Transaction]
    bills: list[Bill]
    house_rules: list[HouseRule]


# ---------- expected results fixture ----------

class CoverCase(_Model):
    roommate_id: str
    amount: float
    date: str
    expect: CoverAnswer


class SplitCase(_Model):
    bill_type: str
    amount: float
    expect: SplitResult


class PaydayCase(_Model):
    roommate_id: str
    amount: float
    expect: PaydayPlan


class AffordCase(_Model):
    item: str
    price: float
    expect: Affordability


class ScriptedProposal(_Model):
    flow: Flow
    title: str
    legs: list[Leg]
    required_approvers: list[str]


class Scripts(_Model):
    rent_group: str
    rent_dm_jordan: str
    couch_group: str
    hello_group: str
    dm_default: str


class Expected(_Model):
    rent_share: float
    split_bill: list[SplitCase]
    can_cover: list[CoverCase]
    payday_plan: list[PaydayCase]
    group_affordability: list[AffordCase]
    next_payday: dict[str, str]
    indicators: dict[str, dict[str, Indicator]]
    proposals: dict[str, ScriptedProposal]  # "rent", "couch"
    scripts: Scripts


# Forward references (Proposal -> HouseRule, BankView -> Profile) resolve once everything exists.
for _m in (Proposal, HouseState, BankView):
    _m.model_rebuild()
