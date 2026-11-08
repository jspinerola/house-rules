# House Rules — requirements

Nov 8, 2026 · @Xander

Requirements for the House Rules prototype, organized so every module can be built and tested on its own branch from the first hour. Product context, contracts and the demo scenario are in the [build plan](https://claude.ai/artifact/7woUBZ8dHDe66nWxHWxArq).

## How nobody waits on another branch

**Only one thing is merged before parallel work starts: the foundation commit** (next section). After that, every module codes against interfaces and stubs that already exist on `main`, never against someone else's unmerged branch.

1. **Contract first.** Every module boundary is a typed interface (Python `Protocol` or TypeScript `type`) plus Pydantic or JSON shapes that live in `contracts/`. Changing one needs a PR touching only `contracts/` and a heads-up to the team.
2. **Every interface ships with a working stub.** The stub returns realistic data from fixtures, so every caller works on day one. Real implementations replace stubs one at a time.
3. **Flags pick real or stub, per module.** Each module has an env flag (`<MODULE>_MODE=stub|real`). `main` must run end to end with every flag on `stub`.
4. **Shared fixtures, not shared state.** The seed scenario (Alex, Sam, Jordan, rent, couch) lives in `fixtures/scenario.json`. Stubs and tests read it; nobody waits for the real database to have data.
5. **Each module is testable alone.** Every requirement below has a standalone done-when that runs with its neighbors stubbed.
6. **Integration is a flag flip, not a merge dependency.** When two real modules are both merged, flip both flags to `real` and run the contract test. No branch ever depends on another branch.

## Foundation commit (the only thing merged first)

One person, or the Cursor one-shot, builds this in about 90 minutes and merges it to `main`. It contains interfaces, stubs and fixtures, and no real logic. Nobody starts a module branch before it lands, and nobody waits for anything after it.

| ID | Requirement | Done when |
| --- | --- | --- |
| F1 | `contracts/models.py`: Pydantic models `ChatIn`, `Reply`, `ChatOut`, `Leg`, `Proposal`, `TraceEvent`, `HouseState`, `BankView`, `Indicator`, `CoverAnswer`, matching the build plan's JSON shapes | `python -c "import contracts.models"` passes |
| F2 | `contracts/interfaces.py`: one `Protocol` per module (signatures in the module requirements below) | Every module in section 4 has a Protocol |
| F3 | `contracts/types.ts`: TypeScript mirror of F1 for the gateway, dashboard and bank app | `tsc --noEmit` passes in all three apps |
| F4 | `fixtures/scenario.json` (roommates, balances, history, bills, house rules, demo date 2026-11-28) and `fixtures/expected.json` (the expected results: $800 rent shares, Jordan `no` until 2026-12-15, electric 60/45/45, couch 3-month plan) | Both load and validate against F1 |
| F5 | `brain/app/stubs/`: a stub class for every Protocol, returning fixture data or `expected.json` answers | Each stub passes its own contract test |
| F6 | `brain/app/registry.py`: `get("nessie")` and so on, choosing stub or real from `<MODULE>_MODE` | All flags default to `stub` |
| F7 | FastAPI app with every route from the build plan (`/chat`, `/state`, `/bank/{id}`, `/demo/*`, `/health`), wired only through the registry | `GET /state` and `GET /bank/jordan` return fixture data |
| F8 | Gateway `sim` mode REPL and a `POST /send` that prints | Typing `#group hi` returns the stub house reply |
| F9 | Empty Next.js dashboard and Expo bank app that render `/state` and `/bank/{id}` as raw JSON | Both show data from the stub brain |
| F10 | `tests/contracts/`: one parametrized test per Protocol that runs against stub and real (real skipped until it exists), plus `tests/test_e2e.py` (rent day, payday fronting, couch) passing on stubs | `pytest` green on `main` |
| F11 | CI on every PR: `pytest`, `tsc --noEmit`, and the Grok Bot review Action | A test PR shows all three checks |
| F12 | `.env.example` with every flag set to `stub`, plus `scripts/setup_reference.sh` for the gitignored workshop repo | Fresh clone plus setup runs the e2e test |

## Dependency map

&#91;embedded content: module dependencies · 15 modules, one shared contracts layer\]

No module imports another module's real code; each one reaches its neighbors through the registry, which hands out stubs until the real one is merged and flagged on.

## Module requirements

Each module lists its interface (in `contracts/interfaces.py`), what its stub does, its flag, and a done-when you can run with every other module stubbed. P0 = needed for the demo, P1 = if time, P2 = stretch.

### M1. Store (database)

- **Interface:** `Store` with `get_roommate(rid)`, `by_handle(handle)`, `transactions(rid, since)`, `add_transaction(...)`, `save_proposal(p)`, `get_proposal(id)`, `pending_for(rid)`, `add_trace(e)`, `recent_trace(n)`, `today()`, `set_today(d)`, `reset()`.
- **Stub:** in-memory, loaded from `fixtures/scenario.json`.
- **Flag:** `DB_MODE=stub|sqlite|tiger`.
- **P0:** SQLite implementation with the same schema SQL as Tiger. **P1:** Tiger Data, with `transactions` as a hypertable and a `monthly_spend` continuous aggregate.
- **Done when:** the Store contract test passes for `sqlite`, and for `tiger` against a Tiger Data instance.

### M2. Indicators

- **Interface:** `Indicators.compute(rid) -> dict[str, Indicator]`, where `Indicator = {value, status: good|watch|risk, inputs}`.
- **Stub:** fixed values from `expected.json` (Jordan's runway under 14 days).
- **Flag:** `INDICATORS_MODE`.
- **P0:** adapter to the workshop `compute_metrics` (8 indicators) plus `runway_days`, `rent_to_income`, `days_to_payday`, `buffer_after(amount)`, all computed from Store data.
- **Done when:** with the Store stubbed, `compute("jordan")` returns all 12 keys and matches `expected.json`.

### M3. Tools (pure math, no LLM)

- **Interface:** `split_bill(type, amount)`, `can_cover(rid, amount, date) -> CoverAnswer{level: ok|tight|no, earliest_date}`, `payday_plan(rid, amount)`, `group_affordability(item, price)`.
- **Stub:** returns the `expected.json` answers.
- **Flag:** `TOOLS_MODE`.
- **P0 rules:** `ok` = balance stays at least $200 until next payday; `tight` = stays at least $0; `no` = goes negative. Fronter = the roommate with the highest `buffer_after`. Affordability tries 1 month, then 3, and picks the first plan where nobody is `no`.
- **Done when:** every expected result in `expected.json` is a passing test, with Store and Indicators stubbed.

### M4. Proposals (approval state machine)

- **Interface:** `create(flow, title, legs, approvers)`, `record_reply(rid, text) -> Proposal|None`, `get(id)`, `pending()`.
- **Stub:** approves on the first "yes".
- **Flag:** `PROPOSALS_MODE`.
- **P0:** yes = yes|y|yep|ok|approve|👍; no = no|n|nah|cancel. A reply applies to that roommate's oldest pending proposal. All yes leads to `approved` and calls `Treasurer.execute`; any no leads to `rejected`. Trace on every change.
- **P1:** amounts under $20 auto-approve after a veto window.
- **Done when:** a test with Treasurer stubbed walks rent from pending to approved to executed.

### M5. Auditor

- **Interface:** `check(text, allowed_numbers, audience) -> {ok, reasons}`.
- **Stub:** always ok.
- **Flag:** `AUDITOR_MODE`.
- **P0:** blocks any number in a message that isn't in `allowed_numbers`. A message to the group may not contain any roommate's balance or income. Blocked drafts are retried once by the caller, then replaced with a template.
- **Done when:** a draft to the group containing Jordan's $310 is blocked, and a correct rent message passes.

### M6. LLM adapter

- **Interface:** `LLM.chat(messages, tools=None) -> {text, tool_calls}`.
- **Stub:** scripted replies keyed by flow (rent, front, couch), so agents work with no API key.
- **Flag:** `LLM_MODE=stub|grok`.
- **P0:** Grok through the OpenAI SDK, `base_url=https://api.x.ai/v1`, model from `GROK_MODEL`, with tool calling. Timeout of 8 s falls back to the stub reply. **P1:** Grok vision for receipts.
- **Done when:** a one-off script calls a tool through Grok and gets a tool call back.

### M7. Personal agent

- **Interface:** `ask(rid, question) -> Release{level, earliest_date}` (all the house agent ever sees) and `dm(rid, text) -> list[Reply]`.
- **Stub:** returns `expected.json` answers and a canned DM.
- **Flag:** `PERSONAL_MODE`.
- **P0:** code decides the answer (Tools `can_cover`); the LLM only words the DM. In a DM, it answers the roommate's own questions with their own numbers.
- **Done when:** with Tools and LLM stubbed, Jordan's `ask` returns only `{level: no, earliest_date: 2026-12-15}`, and his DM explains the fronting plan.

### M8. House agent

- **Interface:** `on_message(sender_rid, text) -> list[Reply]` and `on_event(event) -> list[Reply]`.
- **Stub:** returns the scripted rent and couch messages from fixtures.
- **Flag:** `HOUSE_MODE`.
- **P0:** tools `split_bill`, `group_affordability`, `payday_plan`, `ask_personal`, `create_proposal`. It handles the `rent_due` event and questions like "can we afford a $1,200 couch?" Every outgoing message goes through the Auditor.
- **Done when:** with all its dependencies stubbed, the couch question produces 3 `ask_personal` trace events and a 3-month proposal.

### M9. Nessie client

- **Interface:** `balance(rid)`, `transactions(rid)`, `transfer(from, to, amount, desc) -> id`, `pay_bill(rid, payee, amount, date) -> id`, `purchase(rid, merchant, amount, desc) -> id`, `seed(scenario)`.
- **Stub:** in-memory ledger seeded from `scenario.json`; balances change on every call.
- **Flag:** `NESSIE_MODE=stub|live`.
- **P0:** live client against the Nessie API (confirm endpoint names in their docs first). `seed` creates 3 customers and checking accounts, deposits the starting balances, and stores the Nessie ids. Retries once on 5xx; on failure, returns an error the Treasurer reports.
- **Done when:** the Nessie contract test passes in `live` mode, and a transfer changes both balances in the Nessie API.

### M10. Treasurer

- **Interface:** `execute(proposal_id) -> list[Leg]`, `run_due(today) -> list[Leg]`.
- **Stub:** marks every leg `done` with a fake id.
- **Flag:** `TREASURER_MODE`.
- **P0:** refuses unless the proposal is `approved`. Runs legs dated today or earlier through the Nessie client; future legs stay `pending` until `run_due`. Records Nessie ids, sets `executed` or `failed`, writes trace, and returns a confirmation `Reply` for the group.
- **Done when:** with Nessie stubbed, rent with fronting produces Sam to Alex $800 now, the $2,400 landlord payment now, and Jordan to Alex $800 only after `run_due(2026-12-16)`.

### M11. Brain API and demo control

- **Routes:** `/chat`, `/state`, `/bank/{rid}`, `/demo/reset`, `/demo/trigger`, `/demo/advance`, `/health` (shapes in the build plan). Routes only call modules through the registry.
- **P0:** `/chat` resolves the sender, sends yes/no replies to Proposals, routes other group text to the House agent and DMs to the Personal agent. `/demo/advance` sets the clock and calls `Treasurer.run_due`. `/health` reports every module's mode.
- **Done when:** the e2e test passes with every flag on `stub`, and again with every flag on `real` except `NESSIE_MODE` and `LLM_MODE`.

### M12. Messaging gateway (Photon)

- **Interface:** consumes `POST /chat` and exposes `POST /send {target, text}`.
- **Stub:** `GATEWAY_MODE=sim`, a terminal REPL (`@jordan yes`, `#group can we afford a couch?`).
- **P0:** Photon 2.0 beta via `spectrum-ts`. Registers the house space and each roommate's DM space, persisted to JSON. Typing indicator while waiting on the brain. Dedupes `message.id`. If the brain is down, replies "one sec."
- **P0 fallback:** if there's no dedicated iMessage line, `target: group` fans out to all 3 DMs prefixed "🏠 House:".
- **P1:** tapback 👍 counts as yes. **P2:** voice call on a Photon SMS number for a missing rent approval.
- **Done when:** a fake brain (a 20-line Express server returning canned `ChatOut`) gets real iMessages and its replies arrive on the phones.

### M13. Bank app (Expo)

- **Reads:** `GET /bank/{rid}` every 2 s.
- **P0:** roommate picker, then an account screen with balance, scheduled payments and transactions (newest first). Styled after the Capital One mobile app for the Capital One demo, with a "Demo: Nessie sandbox data" banner, no login fields, and Expo Go only. A new transaction slides in and the balance animates.
- **Done when:** against the stub brain, `POST /demo/trigger` plus 3 stub yeses visibly change Alex's screen within 3 s.

### M14. House view dashboard (Next.js)

- **Reads:** `GET /state` every 2 s.
- **P0:** three columns: roommates (balance, ok/tight/no, next payday) and who owes whom; proposals with an approval check per roommate; agent trace, newest first and colored by agent. Hidden presenter buttons for reset, trigger and advance. P0 fallback view: the combined "house thread" if group chat runs by relay.
- **Done when:** it renders every field of `HouseState` from the stub brain, and the trace updates live during the stub e2e run.

### M15. Dev workflow and Grok Bot

- **P0:** CI (`pytest`, `tsc`) and the Grok review Action on every PR. Cursor is the coding agent for everyone; collect screenshots for Devpost. **P1:** `scripts/grok_seed.py` generates extra receipts and bills into `fixtures/`.
- **Done when:** a PR shows a Grok summary comment and green checks.

## Integration points and branch rules

Integration happens by flipping flags on `main` after both sides are merged, never by waiting on a branch.

| Checkpoint | Flags flipped to real | Proves |
| --- | --- | --- |
| I1 | `DB`, `INDICATORS`, `TOOLS` | Real numbers match `expected.json` |
| I2 | I1 + `PROPOSALS`, `AUDITOR`, `TREASURER` (Nessie still stub) | Rent day and fronting run on real logic |
| I3 | I2 + `PERSONAL`, `HOUSE` (LLM still stub) | Couch fan-out runs on real agents |
| I4 | I3 + `NESSIE=live` | Money moves in Nessie; the bank app shows it |
| I5 | I4 + `LLM=grok`, `GATEWAY=photon` | Full demo from real phones |

If a checkpoint fails, flip the failing module back to `stub` on `main` and keep going. The demo can run at any checkpoint.

**Branch rules**

- One branch per module requirement (e.g. `m9-nessie-live`), cut from `main`, merged within a few hours. Small PRs.
- A branch may only import from `contracts/`, its own module, and the registry. Importing another module's real code directly fails review.
- Need something another module doesn't have yet? Extend that module's **stub** in your own PR (stubs are shared and safe to edit). Add the real behavior to their backlog.
- Contract changes get their own PR touching only `contracts/`, `fixtures/` and the stubs, merged fast, with a heads-up to the team.
- `main` always passes `pytest` with all flags on `stub`. CI enforces this.

## Non-functional requirements

| ID | Area | Requirement |
| --- | --- | --- |
| N1 | Privacy | A group message never contains a roommate's balance, income or merchants. Enforced by the Auditor in code, not by prompts |
| N2 | Safety | No money moves without every required approval; only the Treasurer calls Nessie write endpoints |
| N3 | Correctness | Every number in an agent message comes from a tool output in the same turn (workshop rule: code does the math, the LLM explains) |
| N4 | Latency | Reply in iMessage within 5 s of a message; a "yes" shows up in the bank app within 3 s of execution |
| N5 | Reliability | The full demo runs with any one external service (Grok, Nessie, Photon, Tiger Data) switched to `stub`; one presenter command per fallback |
| N6 | Secrets | API keys only in local `.env` and CI secrets; never in git, the Expo app, or chat |
| N7 | Data | Synthetic data only; a "not financial advice" line on the dashboard and bank app |
| N8 | Observability | Every agent step writes a trace event; `/health` shows each module's mode |
| N9 | Demo control | `/demo/reset` returns everything to the 2026-11-28 starting state in under 5 s |
