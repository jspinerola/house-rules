# AGENTS.md — House Rules

Guidance for humans and coding agents working in this repo. Prefer this file + frozen contracts over inventing new shapes.

## Ground rules

- Read `REQUIREMENTS.md` and `SPEC.md` before any change.
- Only edit files in the module you were asked to work on. Never edit `contracts/` or `fixtures/` unless the task says "contract change".
- Talk to other modules only through `contracts/interfaces.py` and the registry. If you need behavior another module lacks, extend its STUB, not its real code.
- Done = the module's "Done when" passes + `pytest` green with all flags on stub.
- Never put API keys in code; read them from env.

## What we're building

House Rules is an AI roommate money manager in iMessage: split bills by house rules, time payments to payday, check group affordability without leaking balances, move money via Nessie after approvals.

**Hard rule:** flows 1–3 (rent day, payday fronting, couch affordability) work end to end before polish.

**Never cut:** rent-day approvals, personal agents answering ok/tight/no, treasurer → Nessie, auditor.

## Before writing finance logic

1. Search `reference/pnc-workshop` (after `scripts/setup_reference.sh`) and reuse workshop code.
2. Credit and extend — do not rewrite `wellness/` metrics/forecast/validation patterns from scratch.
3. Never edit `reference/`. Working copy lives in `brain/wellness/`.

Workshop reuse map:

| Workshop file | Use for |
| --- | --- |
| `wellness/metrics.py` | 8 deterministic health indicators |
| `wellness/profile.py` | Profile shape; adapt our tables into it |
| `wellness/forecast.py`, `scenarios.py` | Cash forecast / what-if pattern |
| `wellness/tools.py` | Approved-tool registry |
| `wellness/graph.py`, `levels.py` | House agent LangGraph base |
| `wellness/validation.py` | Auditor number checks |
| `wellness/llm.py` | Mock + OpenAI-compatible adapters; add Grok here |

PNC workshop rule judges will look for: **code does the math, the LLM explains, validate before explaining.**

## Architecture (least privilege)

Agents are split by what they may **see** and **do**, not by topic.

| Agent | Lives in | Can see | Can do |
| --- | --- | --- | --- |
| House | Group chat | Shared bills, house rules, what personal agents release | Talk, propose, poll, ask personal agents |
| Personal (×3) | That roommate's DM | Only that roommate's accounts/indicators | Reply ok/tight/no or a date; collect approval |
| Treasurer | Backend only | Approved proposals | **Only** agent with Nessie write access |
| Auditor | Between agents and chat | Drafts, tool outputs, approvals | Block invented numbers, missing approvals, unreleased facts |

Specialists are **tools** the house agent calls (`split_bill`, `group_affordability`, `payday_plan`, `read_receipt`, `watch`) — not separate agents.

### Rules every LLM prompt carries

- Never compute numbers. Call a tool and quote its output.
- Never repeat a roommate's balance, income, or merchants in the group. Only ok, tight, no, or a date.
- Every money movement is a proposal until the required people reply yes.
- Keep iMessage replies to 1–3 sentences.

### Approval rules

- **Owner approves** — person whose money moves replies yes.
- **Everyone approves** — rent goes out only when all shares are confirmed.
- **Small amounts** (P1) — under $20 auto-approve after a 1-hour veto window.
- **Private nudges** — late payer gets a DM, never a public callout.
- **House rules** — a rule set in chat ("Alex has the master, rent is 40/30/30") is a `rule` proposal; everyone approves; no money moves, so the treasurer is not called.
- **Personal preferences** — cushion, savings goal, front cap and notes are set by that roommate in their DM, apply immediately, and never leave that DM. Design: `docs/RULES_AND_PROFILES.md`.

Yes parsing: `yes` | `y` | `yep` | `ok` | `approve` | 👍. No: `no` | `n` | `nah` | `cancel`.

## Parallel work (frozen contracts)

1. **Contracts section is frozen.** Change an endpoint or JSON shape only after telling the whole team and updating docs first.
2. **Mocks behind the same interface.** `LLM_MODE=mock|grok`, `NESSIE_MODE=mock|live`, `GATEWAY_MODE=sim|photon`. Demo must run with all three mocked.
3. **One demo clock.** Only demo endpoints move "today" forward.

Rule for every feature PR: **e2e test must still pass with all mocks on before merge.**

## Ownership

| Owner | Owns | Port / notes |
| --- | --- | --- |
| **A** Data & indicators | `config.py`, `db.py`, `seed.py`, `indicators.py`, `tools.py`, `demo.py`, `wellness/` | Blocks: schema + seed by hour 2 |
| **B** Agents | `main.py`, `agents/*`, `proposals.py`, `trace.py` | Stub A's tools until A lands |
| **C** Photon gateway | `gateway/` | Only depends on `/chat` contract |
| **D** Treasurer & UI | `nessie.py`, `treasurer.py`, `bank-app/`, `dashboard/`, Grok Bot Action | |

## Repo layout (target)

```
brain/                 Python 3.11, FastAPI :8000
  app/main.py          routes only [B]
  app/config.py        env, demo clock [A]
  app/db.py            Tiger + SQLite fallback [A]
  app/seed.py          roommates, history, bills [A]
  app/indicators.py    per-roommate indicators [A]
  app/tools.py         split_bill, can_cover, payday_plan, group_affordability [A]
  app/nessie.py        live + mock client [D]
  app/treasurer.py     executes approved proposals [D]
  app/agents/          llm, house, personal, auditor [B]
  app/proposals.py     proposal + approval state machine [B]
  app/trace.py         dashboard events [B]
  app/demo.py          reset, trigger, advance [A]
  wellness/            from PNC workshop [A]
  tests/
gateway/               TypeScript :8787 [C]
dashboard/             Next.js :3000 [D]
bank-app/              Expo Harbor Bank [D]
```

## Shared contracts (do not drift)

### Demo seed

Clock starts `2026-11-28`. Rent due `2026-12-01`. Amounts USD.

| id | Checking | Income | Next payday |
| --- | --- | --- | --- |
| alex | $4,200 | $5,800 on 1st | 2026-12-01 |
| sam | $2,600 | $1,900 biweekly | 2026-12-05 |
| jordan | $310 | $1,350 on 15th + gigs | 2026-12-15 |

Expected results (pytest must lock these):

- Rent split = $800 each.
- `can_cover(jordan, 800, 2026-11-30)` → no; earliest `2026-12-15`.
- Electric $150 → Sam $60, Alex $45, Jordan $45.
- Couch $400 up front: Alex ok, Sam ok, Jordan no. Over 3 months → Jordan tight → propose 3-month plan.

### Brain HTTP (`:8000`)

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/chat` | `ChatIn` → `ChatOut` (gateway) |
| `GET` | `/state` | `HouseState` (dashboard) |
| `GET` | `/bank/{roommate_id}` | `BankView` (bank app) |
| `POST` | `/demo/reset` | reseed; clock → 2026-11-28 |
| `POST` | `/demo/trigger` | `{event: "rent_due"\|"electric_bill"\|"watch"}` |
| `POST` | `/demo/advance` | `{to: "YYYY-MM-DD"}` runs due scheduled legs |
| `GET` | `/health` | `{ok, llm_mode, nessie_mode}` |

### Gateway HTTP (`:8787`)

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/send` | brain → group or DM proactive text |
| `GET` | `/health` | mode + registered spaces |

### Core JSON shapes

```ts
type ChatIn  = { chat_type: "group" | "dm"; sender_handle: string; text: string; message_id: string; ts: string };
type Reply   = { target: { type: "group" } | { type: "dm"; roommate_id: string }; text: string };
type ChatOut = { replies: Reply[] };

type Leg = {
  type: "transfer" | "scheduled_transfer" | "bill_payment" | "purchase";
  from: string; to?: string; payee?: string;
  amount: number; date: string;
  status: "pending" | "done" | "failed"; nessie_id?: string;
};

type Proposal = {
  id: string; flow: "rent" | "front" | "purchase" | "utility" | "rule";
  title: string; legs: Leg[];
  required_approvers: string[];
  approvals: Record<string, "pending" | "yes" | "no">;
  status: "pending" | "approved" | "executed" | "rejected" | "failed";
  rule?: HouseRule;   // flow "rule" only
};

type HouseState = {
  today: string;
  roommates: { id: string; name: string; balance: number; status: "ok" | "tight" | "no"; next_payday: string }[];
  owes: { from: string; to: string; amount: number; due: string }[];
  proposals: Proposal[];
  trace: TraceEvent[]; // newest first, max 50
  rules: HouseRule[];
};
```

### Python module contracts

```python
# indicators.py [A]
compute(roommate_id) -> dict[str, {"value": float, "status": "good"|"watch"|"risk", "inputs": dict}]
# + runway_days, rent_to_income, days_to_payday, buffer_after(amount)
profile(roommate_id) -> Profile   # private: income pattern, recurring charges, preferences, indicators

# tools.py [A] — pure code, no LLM
split_bill(bill_type, amount, rule=None) -> {"shares": {roommate_id: float}}
can_cover(roommate_id, amount, date) -> {"level": "ok"|"tight"|"no", "earliest_date": str|None, "reason": str|None}
# ok = balance (minus recurring charges before payday) stays >= max(200, min_buffer) + savings_monthly;
# tight >= 0; no = negative; ok -> tight when runway_days is risk. reason is DM-only.
payday_plan(roommate_id, amount) -> {"fronter": roommate_id, "repay_date": str}   # skips fronters over their front_cap
group_affordability(item, price, months_options=[1, 3]) -> {"answers": {...}, "plan": {...}}

# nessie.py [D] — live and mock same class
balance / transactions / transfer / pay_bill / purchase

# treasurer.py [D]
execute(proposal_id) -> list[Leg]   # only if approved; future legs stay pending
run_due(today) -> list[Leg]

# proposals.py [B]
create(...) -> Proposal
record_reply(roommate_id, text) -> Proposal | None  # all yes -> approved -> treasurer.execute (flow "rule": save rule instead)

# store [A] additions
house_rules() / save_house_rule(rule) / delete_house_rule(bill_type)
get_preferences(rid) -> Preferences / save_preferences(rid, prefs)

# auditor.py [B]
check(text, allowed_numbers: set[float], audience: "group"|roommate_id) -> {"ok": bool, "reasons": list[str]}
```

## Env modes

| Key | Values | Notes |
| --- | --- | --- |
| `LLM_MODE` | `mock` \| `grok` | MockLLM scripts the 3 demo flows |
| `NESSIE_MODE` | `mock` \| `live` | Mock writes into local transactions |
| `GATEWAY_MODE` | `sim` \| `photon` | sim = terminal REPL |
| `DB_MODE` | `sqlite` \| `tiger` | skeleton starts on sqlite |
| `BRAIN_URL` | `http://localhost:8000` | gateway, dashboard, bank app |
| `GATEWAY_URL` | `http://localhost:8787` | brain proactive sends |

Never commit `.env`. Use `.env.example`.

## Cut order (if behind)

1. P2 (subscriptions, lease renewal, voice call)
2. Receipt photo split
3. Small-amount auto-approve
4. Chat-set house rules → preload instead
5. Ledger page → post summary into group chat instead

## Coding conventions for agents

- Keep the Photon gateway thin (~150 lines ideal): forward text, post reply, nothing else.
- Prefer small typed functions; match existing module contracts.
- Do not call real Photon / Nessie / xAI APIs unless the task explicitly swaps a mock for live.
- When adding tools, register them in the approved-tool pattern (`wellness/tools.py` / `app/tools.py`).
- Trace every hand-off: asked, answered, proposed, approved, executed, blocked.
- Auditor runs on every outbound reply; group messages must not contain balances or incomes.

## Acceptance smoke (P0 skeleton)

With all mocks on:

1. `POST /demo/reset`, then `/demo/trigger` `{event:"rent_due"}`.
2. Jordan personal agent → no; house proposes Alex fronts Jordan.
3. `/chat` yes from alex, sam, jordan → treasurer executes.
4. `/bank/alex` shows +$800 from Sam and −$2,400 to Maple Court Apartments.
5. `/demo/advance` `{to:"2026-12-16"}` runs Jordan → Alex $800.
6. `#group can we afford a $1,200 couch?` → 3-month plan; three yeses execute it.

Lock this in `brain/tests/test_e2e.py`.
