# House Rules — requirements

Nov 8, 2026 · @Xander

Requirements for the House Rules prototype, organized so every module can be built and tested on its own branch from the first hour. Product context, contracts and the demo scenario are in the [build plan](https://claude.ai/artifact/7woUBZ8dHDe66nWxHWxArq).

## Start here

```bash
git clone <repo> && cd house-rules
./scripts/setup_reference.sh        # gitignored copy of the PNC workshop repo
cp .env.example .env                # every flag on stub
cd brain && pip install -r requirements.txt && cd ..
pytest                              # from the repo root; must be green
```

Then cut your branch from `main`, flip **only your module's flag** to `real` in your `.env`, and build. `pytest` must stay green with all flags on `stub`.

## Status (2026-11-08)

The foundation commit and P0 skeleton are merged to `main` (PR #2, CI green).

| Item | Status |
| --- | --- |
| F1–F12 | Done (CI: `pytest` + `tsc` x3 green; Grok review skips until `XAI_API_KEY` is set) |
| M1 Store | P0 done (sqlite); Tiger Data open |
| M2 Indicators, M3 Tools, M4 Proposals, M5 Auditor | P0 skeleton done; hardening open |
| M7 Personal agent, M8 House agent | P0 skeleton done (code + stub wording); house agent routes group messages via Grok tool calls (keyword fallback); Grok personal-agent routing open |
| M10 Treasurer | P0 done |
| M11 Brain API | Done: route shape tests, JSON errors, env CORS, `/health` modes (`m11-api`) |
| M12 Gateway | Sim and Photon done (`GATEWAY_MODE=photon`): shared-pool DMs, `GATEWAY_FANOUT=1` house relay (one failing phone does not block the rest), `#house` DMs to the house agent, dedupe, brain retry, best-effort typing, `npm test`. Inbound verified on 3 phones; full rent-day run pending Julian being added to the Photon project |
| M14 Dashboard | Unstyled version done |
| M13 Bank app | Done: styled account screen, animated balance and rows, Metro `/brain` proxy over the Expo tunnel (PR #6) |
| M16 Outbox http | Done in brain (gateway down -> JSON 502); REPL check with the sim gateway open |
| M6 LLM (Grok), M9 Nessie live, M15 CI + Grok Bot | Open |

**What's still open, by person**

- **Teammate 2:** Tiger Data (M1 P1), hardening indicators, tools and auditor (M2, M3, M5), dashboard styling (D6 / M14), chat-set house rules (A7 / M8 P1).
- **Teammate 3:** Photon gateway (C2–C7 / M12), switching agents to Grok wording and tool calls (B2, B4 / M6, M8), the watcher (B8), a LangGraph house graph if wanted.
- **Xander:** live Nessie (D2 / M9), Grok Bot secrets in CI (D7 / M15), Devpost (D8).

## How nobody waits on another branch

**Only one thing is merged before parallel work starts: the foundation commit** (next section). After that, every module codes against interfaces and stubs that already exist on `main`, never against someone else's unmerged branch.

1. **Contract first.** Every module boundary is a typed interface (Python `Protocol` or TypeScript `type`) plus Pydantic or JSON shapes that live in `contracts/`. Changing one needs a PR touching only `contracts/` and a heads-up to the team.
2. **Every interface ships with a working stub.** The stub returns realistic data from fixtures, so every caller works on day one. Real implementations replace stubs one at a time.
3. **Flags pick real or stub, per module.** Each module has an env flag (`<MODULE>_MODE=stub|real`). `main` must run end to end with every flag on `stub`.
4. **Shared fixtures, not shared state.** The seed scenario (Xander, Julian, Kevin, rent, couch) lives in `fixtures/scenario.json`. Stubs and tests read it; nobody waits for the real database to have data.
5. **Each module is testable alone.** Every requirement below has a standalone done-when that runs with its neighbors stubbed.
6. **Integration is a flag flip, not a merge dependency.** When two real modules are both merged, flip both flags to `real` and run the contract test. No branch ever depends on another branch.

## Foundation commit (the only thing merged first)

One person, or the Cursor one-shot, builds this in about 90 minutes and merges it to `main`. It contains interfaces, stubs and fixtures, and no real logic. Nobody starts a module branch before it lands, and nobody waits for anything after it.

| ID | Requirement | Done when |
| --- | --- | --- |
| F1 | `contracts/models.py`: Pydantic models `ChatIn`, `Reply`, `ChatOut`, `Leg`, `Proposal`, `TraceEvent`, `HouseState`, `BankView`, `Indicator`, `CoverAnswer`, matching the build plan's JSON shapes | `python -c "import contracts.models"` passes |
| F2 | `contracts/interfaces.py`: one `Protocol` per module (signatures in the module requirements below) | Every module in section 4 has a Protocol |
| F3 | `contracts/types.ts`: TypeScript mirror of F1 for the gateway, dashboard and bank app | `tsc --noEmit` passes in all three apps |
| F4 | `fixtures/scenario.json` (roommates, balances, history, bills, house rules, demo date 2026-11-28) and `fixtures/expected.json` (the expected results: $800 rent shares, Kevin `no` until 2026-12-15, electric 60/45/45, couch 3-month plan) | Both load and validate against F1 |
| F5 | `brain/app/stubs/`: a stub class for every Protocol, returning fixture data or `expected.json` answers | Each stub passes its own contract test |
| F6 | `brain/app/registry.py`: `get("nessie")` and so on, choosing stub or real from `<MODULE>_MODE` | All flags default to `stub` |
| F7 | FastAPI app with every route from the build plan (`/chat`, `/state`, `/bank/{id}`, `/demo/*`, `/health`), wired only through the registry | `GET /state` and `GET /bank/jordan` return fixture data |
| F8 | Gateway `sim` mode REPL and a `POST /send` that prints | Typing `#group hi` returns the stub house reply |
| F9 | Empty Next.js dashboard and Expo bank app that render `/state` and `/bank/{id}` as raw JSON | Both show data from the stub brain |
| F10 | `tests/contracts/`: one parametrized test per Protocol that runs against stub and real (real skipped until it exists), plus `tests/test_e2e.py` (rent day, payday fronting, couch) passing on stubs | `pytest` green on `main` |
| F11 | CI on every PR: `pytest`, `tsc --noEmit`, and the Grok Bot review Action | A test PR shows all three checks |
| F12 | `.env.example` with every flag set to `stub`, plus `scripts/setup_reference.sh` for the gitignored workshop repo | Fresh clone plus setup runs the e2e test |

**F1 helper shapes (added with the foundation):** `Ask{amount, by_date, purpose}`, `Release{level, earliest_date}`, `SplitResult`, `PaydayPlan`, `Affordability{answers, plan | null}`, `AuditResult`, `LLMResult`, `BankTxn`, all in `contracts/models.py`.

**Flag values:** every flag accepts `stub` or `real`. `real` maps to `sqlite` (DB), `grok` (LLM), `live` (Nessie) and `http` (Outbox) where relevant; the specific value can also be set directly. Modes that aren't built yet (`tiger`, Grok calls, Nessie `live`, gateway `photon`) **raise an error instead of falling back**, so a missing implementation is never silent. `/health` returns `{ok, llm_mode, nessie_mode, modes: {<every module>: <mode>}}`.

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

* **Also on the interface:** `roommates()`, `proposals()`, `bill(type)`, `house_rule(type)`.

### M2. Indicators

- **Interface:** `Indicators.compute(rid) -> dict[str, Indicator]`, where `Indicator = {value, status: good|watch|risk, inputs}`.
- **Stub:** fixed values from `expected.json` (Kevin's runway under 14 days).
- **Flag:** `INDICATORS_MODE`.
- **P0:** adapter to the workshop `compute_metrics` (8 indicators) plus `runway_days`, `rent_to_income`, `days_to_payday`, `buffer_after(amount)`, all computed from Store data.
- **Done when:** with the Store stubbed, `compute("jordan")` returns all 12 keys and matches `expected.json`.

### M3. Tools (pure math, no LLM)

- **Interface:** `split_bill(type, amount)`, `can_cover(rid, amount, date) -> CoverAnswer{level: ok|tight|no, earliest_date}`, `payday_plan(rid, amount)`, `group_affordability(item, price)`.
- **Stub:** returns the `expected.json` answers.
- **Flag:** `TOOLS_MODE`.
- **P0 rules:** `ok` = balance stays at least $200 until next payday; `tight` = stays at least $0; `no` = goes negative. Fronter = the roommate with the highest `buffer_after`. Affordability tries 1 month, then 3, and picks the first plan where nobody is `no`.
- **Done when:** every expected result in `expected.json` is a passing test, with Store and Indicators stubbed.

* **Also on the interface:** `next_payday(rid, after) -> date | None`, the first payday strictly after `after`.
* **`can_cover` exactly:** cash = balance − amount − legs already committed out of that account before the next payday. Paydays on or before `date` count as received. `ok` if cash ≥ $200, `tight` if ≥ $0, `no` if < $0. `earliest_date` is set only when the answer is `no`.

### M4. Proposals (approval state machine)

- **Interface:** `create(flow, title, legs, approvers)`, `record_reply(rid, text) -> Proposal|None`, `get(id)`, `pending()`.
- **Stub:** approves on the first "yes".
- **Flag:** `PROPOSALS_MODE`.
- **P0:** yes = yes|y|yep|ok|approve|👍; no = no|n|nah|cancel. A reply applies to that roommate's oldest pending proposal. All yes leads to `approved` and calls `Treasurer.execute`; any no leads to `rejected`. Trace on every change.
- **P1:** amounts under $20 auto-approve after a veto window.
- **Done when:** a test with Treasurer stubbed walks rent from pending to approved to executed.

* **Also on the interface:** `parse(text) -> "yes" | "no" | None`, used by `/chat` routing.
* **Rent with fronting is ONE proposal** (flow `rent`, all 3 approve) with three legs: Julian to Xander $800 now, Xander to Maple Court $2,400 now, Kevin to Xander $800 scheduled 2026-12-16.

### M5. Auditor

- **Interface:** `check(text, allowed_numbers, audience) -> {ok, reasons}`.
- **Stub:** always ok.
- **Flag:** `AUDITOR_MODE`.
- **P0:** blocks any number in a message that isn't in `allowed_numbers`. A message to the group may not contain any roommate's balance or income. Blocked drafts are retried once by the caller, then replaced with a template.
- **Done when:** a draft to the group containing Kevin's $310 is blocked, and a correct rent message passes.

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
- **Done when:** with Tools and LLM stubbed, Kevin's `ask` returns only `{level: no, earliest_date: 2026-12-15}`, and his DM explains the fronting plan.

* **Also on the interface:** `explain(rid, proposal) -> list[Reply]`, the private DM about a proposal (e.g. Kevin's fronting DM).

### M8. House agent

- **Interface:** `on_message(sender_rid, text) -> list[Reply]` and `on_event(event) -> list[Reply]`.
- **Stub:** returns the scripted rent and couch messages from fixtures.
- **Flag:** `HOUSE_MODE`.
- **P0:** tools `split_bill`, `group_affordability`, `payday_plan`, `ask_personal`, `create_proposal`. It handles the `rent_due` event and questions like "can we afford a $1,200 couch?" Every outgoing message goes through the Auditor.
- **Done when:** with all its dependencies stubbed, the couch question produces 3 `ask_personal` trace events and a 3-month proposal.

* **P1: house rules set by chat (build plan A7).** A roommate texts a rule ("Xander has the master, rent should be 40/30/30"); the house agent's tool loop calls `propose_rule`; code validates it, previews the dollar split with `split_bill(..., rule=candidate)` and opens a `rule` proposal everyone must approve. On all yeses, `proposals` saves it with `store.save_house_rule` (no treasurer call). `remove_rule` goes through the same consent. Design: `docs/RULES_AND_PROFILES.md`.
  - Done when: with a scripted LLM, "40/30/30" previews $960 / $720 / $720, three yeses save it, the next rent proposal uses it, a pending rent proposal keeps $800 each, and invalid percents are rejected with a reason.
* **P1: personal profile (build plan A9).** `Indicators.profile(rid)` derives income pattern, side income, recurring charges and spend trend from store history plus executed legs (real Nessie ids), and the roommate sets a cushion, savings goal, front cap or notes in their DM (`set_preference`). `can_cover` and `payday_plan` use them; `Release` is unchanged, so the house still sees only ok / tight / no or a date.
  - Done when: Kevin is `steady_plus_side` with $374.89/mo side income; StreamFlix and Phone Plan are detected as recurring; executed rent changes Kevin's runway; Julian's $2,500 cushion turns the couch answer from ok to tight; Xander's $500 front cap makes Julian the fronter; every locked result in `test_expected.py` is unchanged with no preferences set.
* **P1: receipt split (build plan A8).** Photo to line items via Grok vision (M6), then the house agent asks who shared which items and proposes the paybacks.

- **Couch plan exactly:** Xander buys the $1,200 couch at Couch Co. now; Julian and Kevin each pay Xander $133.33, $133.33 and $133.34 on 2026-11-28, 2026-12-28 and 2027-01-28.

### M9. Nessie client

- **Interface:** `balance(rid)`, `transactions(rid)`, `transfer(from, to, amount, desc) -> id`, `pay_bill(rid, payee, amount, date) -> id`, `purchase(rid, merchant, amount, desc) -> id`, `seed(scenario)`.
- **Stub:** in-memory ledger seeded from `scenario.json`; balances change on every call.
- **Flag:** `NESSIE_MODE=stub|live`.
- **P0:** live client against the Nessie API (confirm endpoint names in their docs first). `seed` creates 3 customers and checking accounts, deposits the starting balances, and stores the Nessie ids. Retries once on 5xx; on failure, returns an error the Treasurer reports.
- **Done when:** the Nessie contract test passes in `live` mode, and a transfer changes both balances in the Nessie API.

* **Also on the interface:** `deposit(rid, amount, description) -> id`. `/demo/advance` credits every payday it crosses (Xander 12-01, Julian 12-05, Kevin 12-15), so Kevin has $860 after repaying on 12-16.

### M10. Treasurer

- **Interface:** `execute(proposal_id) -> list[Leg]`, `run_due(today) -> list[Leg]`.
- **Stub:** runs due legs through the stub Nessie and leaves future legs pending (it no longer marks every leg done).
- **Flag:** `TREASURER_MODE`.
- **P0:** refuses unless the proposal is `approved`. Runs legs dated today or earlier through the Nessie client; future legs stay `pending` until `run_due`. Records Nessie ids, sets `executed` or `failed`, writes trace, and returns a confirmation `Reply` for the group.
- **Done when:** with Nessie stubbed, rent with fronting produces Julian to Xander $800 now, the $2,400 landlord payment now, and Kevin to Xander $800 only after `run_due(2026-12-16)`.

### M11. Brain API and demo control

- **Routes:** `/chat`, `/state`, `/bank/{rid}`, `/demo/reset`, `/demo/trigger`, `/demo/advance`, `/health` (shapes in the build plan). Routes only call modules through the registry.
- **P0:** `/chat` resolves the sender, sends yes/no replies to Proposals, routes other group text to the House agent and DMs to the Personal agent. `/demo/advance` sets the clock and calls `Treasurer.run_due`. `/health` reports every module's mode.
- **Done when:** the e2e test passes with every flag on `stub`, and again with every flag on `real` except `NESSIE_MODE`, `LLM_MODE` and `OUTBOX_MODE`.

* **E2E test:** three tests (rent day, payday fronting, couch), each starting from `/demo/reset`. CI runs the file twice: all `stub`, and all `real` except `NESSIE_MODE`, `LLM_MODE` and `OUTBOX_MODE`.

### M12. Messaging gateway (Photon)

- **Interface:** consumes `POST /chat` and exposes `POST /send {target, text}`.
- **Stub:** `GATEWAY_MODE=sim`, a terminal REPL (`@jordan yes`, `#group can we afford a couch?`).
- **P0:** Photon 2.0 beta via `spectrum-ts`. Registers the house space and each roommate's DM space, persisted to JSON. Typing indicator while waiting on the brain. Dedupes `message.id`. If the brain is down, replies "one sec."
- **P0 fallback:** if there's no dedicated iMessage line, `target: group` fans out to all 3 DMs prefixed "🏠 House:".
- **P1:** tapback 👍 counts as yes. **P2:** voice call on a Photon SMS number for a missing rent approval.
- **Done when:** a fake brain (a 20-line Express server returning canned `ChatOut`) gets real iMessages and its replies arrive on the phones.

* **Sim REPL:** start the brain with `OUTBOX_MODE=http` so pushed messages reach it. Commands: `@alex <dm>`, `#group <text>`, `@sam #group <text>` (group message sent as Julian), `/reset`, `/trigger rent_due`, `/advance YYYY-MM-DD`, `/state`.

### M13. Bank app (Expo)

- **Reads:** `GET /bank/{rid}` every 2 s.
- **P0:** roommate picker, then an account screen with balance, scheduled payments and transactions (newest first). Styled after the Capital One mobile app for the Capital One demo, with no login fields, and Expo Go only. A new transaction slides in and the balance animates.
- **Done when:** against the stub brain, `POST /demo/trigger` plus 3 stub yeses visibly change Xander's screen within 3 s.

### M14. House view dashboard (Next.js)

- **Reads:** `GET /state` every 2 s.
- **P0:** three columns: roommates (balance, ok/tight/no, next payday) and who owes whom; proposals with an approval check per roommate; agent trace, newest first and colored by agent. Hidden presenter buttons for reset, trigger and advance. P0 fallback view: the combined "house thread" if group chat runs by relay.
- **Done when:** it renders every field of `HouseState` from the stub brain, and the trace updates live during the stub e2e run.

### M15. Dev workflow and Grok Bot

- **P0:** CI (`pytest`, `tsc`) and the Grok review Action on every PR. Cursor is the coding agent for everyone; collect screenshots for Devpost. **P1:** `scripts/grok_seed.py` generates extra receipts and bills into `fixtures/`.
- **Done when:** a PR shows a Grok summary comment and green checks.

### M16. Outbox

- **Interface:** `send(reply: Reply)`.
- **Stub:** records sent replies in memory (tests read them).
- **Flag:** `OUTBOX_MODE=stub|http`.
- **P0:** `http` POSTs each reply to the gateway's `POST /send`. The Treasurer's confirmations and `/demo/trigger` messages go through the Outbox, never straight to the gateway.
- **Done when:** with the brain on `OUTBOX_MODE=http` and the gateway in sim mode, `/demo/trigger rent_due` prints the house message in the REPL.

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
