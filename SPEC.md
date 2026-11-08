# House Rules — build plan

Nov 7, 2026 · @Xander

## Summary

**House Rules is an AI money manager that lives in your roommates' iMessage group chat.** It splits bills by your house rules, times payments to each person's payday, answers "can we afford this as a group?" without anyone revealing their balance, and moves the money through the bank once the right people reply yes.

Unlike Splitwise-style apps that track IOUs, House Rules **actually moves money** (Nessie), **checks financial health before asking anyone to pay** (PNC), and **needs no app**, because the group chat is the interface (Photon).

| Track or prize | What we show |
| --- | --- |
| PNC 360° Financial Health Navigator | Per-roommate indicators (runway, rent-to-income, payday timing) and a group affordability check, computed by code and explained by the LLM |
| Photon (Best Use of Photon API) | The whole product runs in iMessage: group chat, private DMs, polls, approvals by reply |
| Capital One Best Use of Nessie | Shared bills, transfers, scheduled paybacks and purchases as real Nessie API calls |
| SpaceXSI raffle (Cursor + Grok Bot) | Built in Cursor; Grok powers the agents and a Grok Bot automation in our dev workflow |

Previously explored and dropped: the family version ("Need to Know"). Its consent and privacy ideas carry over as the personal agents.

## Users and core flows

**Demo household: a 3-bedroom apartment, $2,400/mo rent (synthetic data only)**

| Roommate | Situation |
| --- | --- |
| Alex | Lease holder; landlord bill comes from Alex's account. Steady salary, paid on the 1st. |
| Sam | Works from home, so the house rule is that Sam pays 40% of electric. Paid biweekly. |
| Jordan | Part-time plus gig income, paid on the 15th. Runway is tight at month start. |

**Flows, with who approves**

| # | Flow | Approval | Nessie calls | Priority |
| --- | --- | --- | --- | --- |
| 1 | **Rent day.** "Rent is $2,400 Friday. $800 each to Alex, then Alex pays the landlord." | Everyone (all 3 yes) | 2 transfers, 1 bill payment | P0 |
| 2 | **Payday timing.** Jordan's runway shows he can't pay until the 15th. "Alex fronts Jordan's $800 now; Jordan auto-repays on the 16th." Group never sees Jordan's balance. | Alex (fronts) + Jordan (agrees to repay) | 1 transfer now, 1 scheduled transfer | P0 |
| 3 | **Group affordability.** "Can we afford a $1,200 couch?" Each personal agent answers ok, tight or no. House agent proposes $400 each over 3 months. | Majority poll, then each payer | 3 scheduled transfers, 1 purchase | P0 |
| 4 | **Utility split.** Electric bill arrives; split by the house rule (Sam 40%). | Each payer | Transfers | P1 |
| 5 | **Receipt photo.** Someone texts a grocery receipt; agent asks who shared what. | Each payer | Transfers | P1 |
| 6 | **Duplicate subscriptions.** All 3 pay for the same streaming service; propose one shared plan. | Each person cancels their own | Bill changes | P2 |
| 7 | **Lease renewal.** "Can we take $2,700?" Each personal agent checks the 30% rent-to-income rule, shares status only. | None (information only) | Reads only | P2 |

**Approval rules (shown to judges)**

- **Owner approves:** the person whose money moves replies yes.
- **Everyone approves:** rent goes out only when all shares are confirmed.
- **Small amounts:** under $20 auto-approves after a 1-hour veto window.
- **Private nudges:** a late payer gets a DM, never a public callout.

## Agents

Agents are split by **what they may see and do**, not by topic. That gives each one a real reason to exist and gives judges a least-privilege story. All LLM agents run on Grok through the workshop's OpenAI-compatible adapter.

| Agent | Lives in | Can see | Can do |
| --- | --- | --- | --- |
| House agent | Group chat | Shared bills, house rules, whatever personal agents release | Talk, propose plans, run polls, ask personal agents |
| Personal agent (one per roommate) | That roommate's DM | Only that roommate's accounts and indicators | Answer the house agent with ok, tight or no (or a date like "can pay on the 16th"); collect that roommate's approval |
| Treasurer | No chat; backend only | Approved proposals only | **The only agent with Nessie write access:** transfers, scheduled paybacks, bills, purchases, retries |
| Auditor (code, not an LLM) | Between every agent and the chat | Draft messages, tool outputs, approvals | Blocks invented numbers, missing approvals, and anything a personal agent didn't release |

**Specialists: tools the house agent calls, not separate agents**

- `split_bill(bill, rules)`: applies house rules and proration.
- `read_receipt(image)`: Grok vision to line items (P1).
- `group_affordability(item, price)`: fans out to personal agents and combines their answers.
- `payday_plan(member, amount)`: finds the earliest payday that keeps runway above a floor.
- `watch()`: runs on a timer, e.g. "rent in 3 days and Sam's checking won't cover it" leads to a private DM to Sam.

**Rules every prompt carries**

- Never compute numbers. Call a tool and quote its output.
- Never repeat a roommate's balance, income or merchants in the group. Only ok, tight, no, or a date.
- Every money movement is a proposal until the required people reply yes.
- Keep iMessage replies to 1–3 sentences.

## Requirements

**P0: must work in the demo**

- Photon gateway: agent number in an existing group chat plus a DM per roommate; typing indicator while tools run.
- Household seed: 3 roommates from the workshop's synthetic customers, mirrored into Nessie (customers, checking accounts, landlord as a merchant or payee).
- Indicators per roommate, by code: the workshop's 8 plus `runway_days`, `rent_to_income`, `next_payday`, `can_cover(amount, date)`.
- Flows 1–3 end to end, including approvals parsed from replies ("yes", "y", thumbs-up tapback).
- Treasurer executes Nessie transfers, scheduled paybacks and the purchase; echoes the exact amounts before and after.
- Auditor blocks any number not from a tool and any action without its approvals.
- Ledger page: house balance sheet, who owes what, pending approvals, and the agent hand-offs (house agent asked, personal agents answered, treasurer executed).

**P1: if on schedule**

- Utility split with house rules set by chat ("Sam pays 40% of electric"), parsed into a rules table and confirmed.
- Receipt photo split.
- Watcher nudges by DM before rent day.
- Small-amount auto-approve with veto window.

**P2: stretch**

- Duplicate subscription finder.
- Lease-renewal affordability.
- Photon voice call to a roommate who hasn't approved rent by the deadline.

## Architecture

Two services: a thin TypeScript gateway for Photon and a Python brain built on the PNC workshop toolkit. Grok is the model behind every LLM agent; Nessie is the bank.

&#91;embedded content: House Rules architecture · Photon, agents, Nessie, Grok\]

Personal agents never post in the group; the house agent only gets what they release, and the auditor checks every message on the way out.

**Reuse from the [PNC workshop repo](https://github.com/devfulcrum/pnc-utd-hackathon-2026)**

- `wellness/profile.py`, `metrics.py`, `forecast.py`: per-roommate profile, the 8 indicators, cash forecast to next payday.
- `wellness/tools.py`: approved-tool registry. Add the specialist tools here.
- `wellness/graph.py`: LangGraph supervisor flow. Becomes the house agent's graph.
- `wellness/validation.py`: base for the auditor.
- `wellness/llm.py`: the OpenAI adapter. Point it at xAI's OpenAI-compatible endpoint for Grok (verify in hour 0).
- `Lab_Package/data/*.csv`: pick 3 synthetic customers as the roommates.

**Photon** ([docs](https://photon.codes/docs)): `spectrum-ts` cloud iMessage provider on Node or Bun, no Mac needed. Keys `SPECTRUM_PROJECT_ID` and `SPECTRUM_PROJECT_SECRET` from [app.photon.codes](https://app.photon.codes). Receive with `for await (const [space, message] of app.messages)`, reply with `space.send(...)`. Cloud lines work in existing group chats, so a teammate creates the group and adds the agent's number.

**Nessie** ([nessieisreal.com](https://nessieisreal.com/); verify endpoint names at hour 0): `POST /customers`, `POST /customers/{id}/accounts`, `POST /accounts/{id}/transfers`, `POST /accounts/{id}/bills`, `POST /accounts/{id}/purchases`, and the matching GETs for the ledger page.

**Data model (SQLite)**

| Table | Key fields |
| --- | --- |
| `roommates` | id, name, photon\_handle, nessie\_account\_id, payday\_rule |
| `house_rules` | id, bill\_type, split (e.g. Sam 40%), source\_text, confirmed\_by |
| `proposals` | id, flow, amounts, required\_approvers, status |
| `approvals` | proposal\_id, roommate\_id, reply\_text, ts |
| `ledger` | ts, agent, event (asked, answered, executed), detail, nessie\_id |

**Stack**

| Part | Choice |
| --- | --- |
| Brain | Python 3.11, FastAPI, LangGraph, pandas, SQLite (workshop toolkit) |
| LLM | Grok via the `openai` SDK with xAI's base URL, on the team's xAI account; `mock` adapter as fallback |
| Photon gateway | TypeScript on Node or Bun, `spectrum-ts` |
| Bank app (demo) | **React Native with Expo**, run in Expo Go; read-only; fictional bank name; reads balances from FastAPI, which proxies Nessie (keeps the key off the phone) |
| House view dashboard | Next.js + Tailwind (fork `Lab_Package/web_demo`), agent trace plus who-owes-what |
| Dev workflow | Cursor for all coding; Grok Bot GitHub Action on each PR |

**Database: [Tiger Data](https://mlh.link/tigerdata)** (managed Postgres with TimescaleDB), for the MLH Best Use of Tiger Data prize. Transactions and balances are time-series, so `transactions` is a hypertable, and monthly spend and income per roommate are continuous aggregates that feed the indicators. `DB_MODE=sqlite` stays as the offline fallback behind the same `db.py`.

## Qualification checklist

**PNC 360° Financial Health Navigator**

- [ ] 3+ health indicators visible (we show 12) with code-computed values
- [ ] A forecast (runway to next payday) and a what-if (couch affordability)
- [ ] Clear split between calculated facts and AI explanation on the ledger page
- [ ] Demo uses only synthetic data; "not financial advice" line in the footer

**Photon**

- [ ] Agent runs on a Photon iMessage line via `spectrum-ts`
- [ ] Group chat and DMs both used; polls or tapbacks used for approvals
- [ ] Built on Photon 2.0 beta and live on iMessage. Judged on Vision, Craft, Depth and Traction; prizes $700 winner, $300 runner-up, $400 best voice agent

**Capital One Nessie**

- [ ] At least 4 endpoint types used live: accounts, transfers, bills, purchases
- [ ] Balances on the ledger page come from Nessie, not our database

**SpaceXSI raffle (Cursor + Grok Bot)**

- [ ] Every teammate codes in Cursor as the main AI coding agent; take a few screenshots for the write-up
- [ ] Grok Bot automation in the workflow. Our plan: a GitHub Action that sends each PR diff to Grok and posts a summary plus a risk check as a PR comment, and a script that has Grok generate new synthetic receipts and bills for test data. The product's agents also run on Grok.
- [ ] Confirm with MLH what counts as "Grok Bot" (a specific product, or any Grok-powered automation?)
- [ ] Devpost description has a "How we used Cursor and Grok Bot" section
- [ ] Opt in to the "Make it Legendary with SpaceXSI" raffle when submitting

**MLH Best Use of Tiger Data**

- [ ] Brain runs on Tiger Data in the demo (`DB_MODE=tiger`)
- [ ] `transactions` is a hypertable; at least one continuous aggregate (monthly spend per roommate) feeds an indicator
- [ ] Devpost explains why time-series fits: balances, paydays and runway are all about time

**General**

- [ ] Confirm whether Photon and Nessie count toward the "up to two" company tracks; if they do, enter PNC + Photon and mention Nessie in the write-up
- [ ] Public GitHub repo, Devpost submission, 2-minute demo video

## Build plan

Hours count from when you start building. The plan is for 3 people, all in Cursor. Hard rule: **flows 1–3 work end to end, ugly, by hour 12.**

| Person | Role | Owns (task ids from the Build spec) |
| --- | --- | --- |
| **Xander** | Bank and money movement | Nessie client and seeding, treasurer, `/bank` endpoint, the Expo bank app, Grok Bot GitHub Action, Devpost and demo video (D1, D2, D3, D5, D7, D8; `/bank` half of D4) |
| Teammate 2 | Brain data and house view | Tiger Data and SQLite schema, seed, demo clock, indicators, tools, proposals state machine, auditor, `/state`, dashboard (A1 to A8, B3, B6, `/state` half of D4, D6) |
| Teammate 3 | Agents and iMessage | Photon gateway, Grok adapter, house and personal agents, `/chat`, trace, watcher (C1 to C8, B1, B2, B4, B5, B7, B8) |

**Milestones**

1. **Hour 0–1: keys and hello world.** Photon project and line, Nessie key, Grok API key. Echo bot answering in a test group chat. Repo set up from the workshop toolkit, opened in Cursor.
2. **Hour 1–4: data and pipes.** 3 roommates seeded in Nessie and local data. New indicators with unit tests. Gateway forwards messages to `POST /chat`. Grok Bot PR Action live (it then runs on every PR all night).
3. **Hour 4–8: agents.** House agent with `split_bill`, `group_affordability`, `payday_plan`. Personal agents answering ok, tight or no. Auditor checks. Treasurer transfer and scheduled transfer.
4. **Hour 8–12: flows 1–3 end to end.** Rent day, payday fronting, couch vote, all from real iMessage replies to real Nessie calls.
5. **Hour 12–16: ledger page and P1.** Ledger page with agent hand-off trace. Utility split with chat-set house rules. Watcher DMs.
6. **Hour 16–20: polish.** Message wording, tapbacks, typing indicators. Record the backup demo video. Rehearse 3 times.
7. **Hour 20–24: submit.** Feature freeze at hour 20. Devpost with the Cursor + Grok Bot section, raffle opt-in, final rehearsal.

**Cut list, in order**

1. P2 features (subscriptions, lease renewal, voice call)
2. Receipt photo split
3. Small-amount auto-approve
4. House rules set by chat: preload them instead
5. Ledger page: post the summary into the group chat instead

Never cut: rent-day approvals, personal agents answering ok/tight/no, treasurer to Nessie, auditor.

## Demo script, risks and open questions

**3-minute demo** (two phones on a document camera or mirrored, ledger page on the projector)

1. **Hook (15 s):** "Every apartment has a group chat, and every group chat has someone chasing rent."
2. **Rent day (45 s):** house agent posts rent. Alex and Sam reply yes. Jordan's personal agent DMs him privately and proposes payday fronting. Alex approves fronting. Nessie balances move on the ledger.
3. **The couch (60 s):** "Can we afford a $1,200 couch?" The ledger shows the house agent asking 3 personal agents: ok, ok, tight. The proposal becomes $400 each over 3 months. The poll passes, and the treasurer schedules it in Nessie.
4. **Under the hood (30 s):** the agent roster split by permissions, the treasurer as the only agent that can move money, the auditor blocking an invented number.
5. **Close (30 s):** "No app, no IOUs, nobody's balance in the group chat. Built in Cursor, powered by Grok, banking on Nessie."

**Risks and fallbacks**

| Risk | Fallback |
| --- | --- |
| Photon or venue Wi-Fi fails at judging | Phone hotspot; recorded backup video; a terminal chat that hits the same `/chat` endpoint |
| Nessie slow or down | `NESSIE_MODE=mock` stub with the same interface |
| Grok API slow or rate-limited | Workshop `mock` adapter with scripted replies for the 3 demo flows |
| Agent leaks a balance into the group | The auditor strips any number not on the personal agent's release list, in code |
| Judges see "Splitwise in iMessage" | Lead with payday fronting and the group affordability fan-out, which Splitwise can't do |
| Python and TypeScript split slows you down | Keep the gateway under \~150 lines: forward text, post reply, nothing else |

**Open questions**

- [ ] Does "Grok Bot" mean a specific xAI product? Ask MLH before hour 1.
- [ ] Do Photon and Nessie count toward the two company tracks?
- [ ] Photon judging criteria and line limits (messages per minute).
- [ ] Names for Teammates 2 and 3 (team of 3: Xander plus two).

**References:** [PNC workshop repo](https://github.com/devfulcrum/pnc-utd-hackathon-2026) · [Photon docs](https://photon.codes/docs) · [Nessie](https://nessieisreal.com/) · earlier family version: [Need to Know PRD](https://claude.ai/artifact/XADa3WvAwyYKFFPavAVnPW)

# Build spec

**Source of truth:** module boundaries, stubs, flags and acceptance criteria live in [House Rules — requirements](https://claude.ai/artifact/5GdRuyuvd6fknrcD4QagtB) (modules M1–M15, foundation commit F1–F12). This spec adds the scenario, JSON shapes and workstream lists. Where the two differ, the requirements doc wins. Put both in the repo as `SPEC.md` and `REQUIREMENTS.md`.

**Status (2026-11-08):** the foundation commit and P0 skeleton are built on branch `foundation` (PR open to `main`). F1–F12 are done except F11 (CI), which waits for green checks. P0 skeletons are done for M1 (sqlite), M2, M3, M4, M5, M7, M8, M10 and M11, plus sim and unstyled versions of M12, M13 and M14. What's still open:

- **Teammate 2:** Tiger Data (M1 P1), hardening indicators, tools and auditor, dashboard styling (D6), chat-set house rules (A7).
- **Teammate 3:** Photon gateway (C2–C7), switching agents to Grok wording and tool calls (B2, B4), the watcher (B8), a LangGraph house graph if wanted.
- **Xander:** live Nessie (D2), bank app styling (D5), Grok Bot secrets in CI (D7), Devpost (D8).

New teammates: follow **Start here** in the requirements doc.

**How to use this spec:** first, one-shot a skeleton where every external service is mocked (LLM, Nessie, Photon). Rent day should then run end to end from a terminal within the first 2 hours. After that, each person replaces one mock with the real thing and adds features one at a time, without breaking the contracts below.

**Three rules that let 4 people work in parallel**

1. **The contracts section is frozen.** Change an endpoint or JSON shape only after telling the whole team, and update this doc first.
2. **Every external service has a mock behind the same interface.** `LLM_MODE=mock|grok`, `NESSIE_MODE=mock|live`, and the gateway's `sim` mode (a terminal chat). The demo must still run with all three set to mock.
3. **One demo clock.** The brain has a fake "today" that only the demo endpoints move forward, so scheduled paybacks can be shown in seconds.

## Starter code: the PNC workshop repo

The brain starts from PNC's workshop toolkit: **[github.com/devfulcrum/pnc-utd-hackathon-2026](https://github.com/devfulcrum/pnc-utd-hackathon-2026)**. Copy it in; don't rewrite it.

```bash
cd house-rules
# full read-only copy so Cursor's agent can index and search it
git clone --depth 1 https://github.com/devfulcrum/pnc-utd-hackathon-2026 reference/pnc-workshop
rm -rf reference/pnc-workshop/.git
# working copy of the toolkit that we edit
cp -r reference/pnc-workshop/wellness brain/wellness
cat reference/pnc-workshop/requirements.txt >> brain/requirements.txt
```

| Workshop file | What we use it for |
| --- | --- |
| `wellness/metrics.py` | The 8 deterministic health indicators (emergency fund months, DTI, savings rate, utilization, net worth, debt-to-asset, housing ratio, liquidity ratio) |
| `wellness/profile.py` | The unified profile shape; A writes an adapter from our tables into it |
| `wellness/forecast.py`, `scenarios.py` | Cash forecast to next payday; pattern for our what-if tools |
| `wellness/tools.py` | Approved-tool registry pattern for the specialist tools |
| `wellness/graph.py`, `levels.py` | LangGraph supervisor, tool, validator, coach flow; base for the house agent |
| `wellness/validation.py` | Base for the auditor's number check |
| `wellness/llm.py` | Mock and OpenAI-compatible adapters; add `GrokLLM` here |
| `Lab_Package/data/*.csv` | 30 synthetic customers with 24 months of transactions; optional source for seed history |
| `Lab_Package/web_demo/frontend` | Next.js app to fork for the dashboard |
| `docs/WORKSHOP.md` | PNC's rules: code does the math, the LLM explains, validate before explaining. Judges will look for these |

**`reference/` is gitignored, so it isn't committed.** Put the clone lines above in `scripts/setup_reference.sh` and have every teammate run it once after cloning. Add `reference/` to `.gitignore`. The copied `brain/wellness/` stays committed, since that's our working code.

**Make sure Cursor still searches it.** Cursor may skip gitignored files when indexing. After running the script, ask Cursor's agent to "search reference/pnc-workshop for compute\_metrics." If it can't find it, add a `.cursorignore` containing `!reference/` (re-includes it), or turn on indexing of gitignored files in Cursor's settings. `@reference/pnc-workshop/...` file mentions in chat work either way.

Never edit `reference/`. Add a `.cursorrules` line: "Before writing finance logic, search reference/pnc-workshop and reuse it." Credit the workshop repo in the README and on Devpost.

## Repo layout and environment

One public monorepo, `house-rules`. The owner of each folder is in brackets.

```text
house-rules/
  brain/                      Python 3.11, FastAPI, port 8000
    app/main.py               routes only [B]
    app/config.py             env loading, demo clock [A]
    app/db.py                 Tiger Data schema + SQLite fallback [A]
    app/seed.py               roommates, history, bills [A]
    app/indicators.py         per-roommate indicators [A]
    app/tools.py              split_bill, can_cover, payday_plan, group_affordability [A]
    app/nessie.py             NessieClient live + mock [D]
    app/treasurer.py          executes approved proposals [D]
    app/agents/llm.py         GrokLLM + MockLLM [B]
    app/agents/house.py       group-chat agent [B]
    app/agents/personal.py    per-roommate agent [B]
    app/agents/auditor.py     message + action checks [B]
    app/proposals.py          proposal + approval state machine [B]
    app/trace.py              trace events for the dashboard [B]
    app/demo.py               reset, trigger, advance clock [A]
    wellness/                 copied from the PNC workshop repo [A]
    tests/                    pytest per module [owner of module]
  gateway/                    TypeScript, Node 20 or Bun, port 8787 [C]
    src/index.ts              Photon mode
    src/sim.ts                terminal sim mode
  bank-app/                   Expo (React Native) [D]
  dashboard/                  Next.js + Tailwind, port 3000 [D]
  scripts/grok_seed.py        Grok-generated receipts and bills [D]
  .github/workflows/grok-review.yml   Grok Bot PR review [D]
  .env.example
```

Also at the repo root, from the requirements doc: `contracts/` (models, interfaces, `types.ts`), `fixtures/` (`scenario.json`, `expected.json`), plus `brain/app/stubs/` and `brain/app/registry.py`. Every module flag is `<MODULE>_MODE` and defaults to `stub`; where this doc says `mock`, read `stub`.

**`.env` keys** (copy `.env.example`; never commit `.env`)

| Key | Example | Used by |
| --- | --- | --- |
| `LLM_MODE` | `mock` or `grok` | brain |
| `XAI_API_KEY` | from console.x.ai | brain, Action (as secret) |
| `GROK_MODEL` | model id from the xAI console | brain |
| `NESSIE_MODE` | `mock` or `live` | brain |
| `NESSIE_API_KEY` | from nessieisreal.com | brain |
| `NESSIE_BASE_URL` | `http://api.nessieisreal.com` (verify) | brain |
| `SPECTRUM_PROJECT_ID`, `SPECTRUM_PROJECT_SECRET` | from app.photon.codes | gateway |
| `GATEWAY_MODE` | `sim` or `photon` | gateway |
| `BRAIN_URL` | `http://localhost:8000` | gateway, dashboard, bank app |
| `GATEWAY_URL` | `http://localhost:8787` | brain (for proactive messages) |
| `ALEX_HANDLE`, `SAM_HANDLE`, `JORDAN_HANDLE` | teammates' iMessage phone numbers or emails | brain seed |

Database keys: `DB_MODE` = `sqlite` or `tiger` (skeleton starts on `sqlite`); `DATABASE_URL` = the Tiger Data Postgres connection string from the Tiger console (used by brain only).

Outbox key: `OUTBOX_MODE` = `stub` or `http` (brain only; `http` needs `GATEWAY_URL`).

**Run everything**

```bash
cd brain && pip install -r requirements.txt && python -m app.seed && uvicorn app.main:app --port 8000
cd gateway && npm i && GATEWAY_MODE=sim npm run dev      # terminal chat; photon mode for real iMessage
cd dashboard && pnpm i && pnpm dev
cd bank-app && npx expo start --tunnel
```

## Shared contracts (frozen)

### Demo scenario and seed data

The demo clock starts on **2026-11-28**. Rent is due **2026-12-01**. All amounts are USD.

| id | Name | Starting checking | Income | Next payday | Notes |
| --- | --- | --- | --- | --- | --- |
| `alex` | Alex | $4,200 | $5,800 salary, 1st of month | 2026-12-01 | Lease holder; pays the landlord |
| `sam` | Sam | $2,600 | $1,900 biweekly | 2026-12-05 | House rule: 40% of electric |
| `jordan` | Jordan | $310 | $1,350 on the 15th, plus gig deposits | 2026-12-15 | Can't cover $800 before payday |

Shared items: landlord **Maple Court Apartments**, rent **$2,400/mo** (bill on Alex's account). Electric bill **$150**, arrives on demand. Couch from **Couch Co.**, **$1,200**. Seed 3 months of synthetic history per roommate (paychecks, groceries, subscriptions) so indicators have something to work with.

Expected results, which the tests should check:

- Rent split = $800 each.
- `can_cover(jordan, 800, 2026-11-30)` = `no`, earliest date 2026-12-15.
- Electric split = Sam $60, Alex $45, Jordan $45.
- `Couch at $400 each up front: Alex ok, Sam ok, Jordan no. Over 3 months ($133.33/mo each): Jordan tight, so the house agent proposes the 3-month plan.`

### Brain HTTP API (port 8000)

| Method + path | Body / query | Returns | Caller |
| --- | --- | --- | --- |
| `POST /chat` | `ChatIn` | `ChatOut` | gateway |
| `GET /state` | none | `HouseState` | dashboard |
| `GET /bank/{roommate_id}` | none | `BankView` | bank app |
| `POST /demo/reset` | none | `{ok}`; reseeds DB, clock back to 2026-11-28 | presenter |
| `POST /demo/trigger` | `{event: "rent_due" \| "electric_bill" \| "watch"}` | `{ok}`; house agent posts proactively | presenter |
| `POST /demo/advance` | `{to: "2026-12-16"}` | `{ok, executed: [...]}`; runs due scheduled legs | presenter |
| `GET /health` | none | `{ok, llm_mode, nessie_mode}` | everyone |

### Gateway HTTP API (port 8787)

| Method + path | Body | Purpose |
| --- | --- | --- |
| `POST /send` | `{target: {type: "group"} \| {type: "dm", roommate_id}, text}` | Brain pushes proactive messages (rent due, executed, nudges) |
| `GET /health` | none | `{ok, mode, group_registered, dms_registered: [...]}` |

The gateway keeps the map from `group` and each `roommate_id` to a Photon space. The group registers on the first message seen in the group chat. A DM registers when that roommate texts the agent once ("hi").

### JSON shapes

```ts
type ChatIn  = { chat_type: "group" | "dm"; sender_handle: string; text: string; message_id: string; ts: string };
type Reply   = { target: { type: "group" } | { type: "dm"; roommate_id: string }; text: string };
type ChatOut = { replies: Reply[] };

type Leg = {
  type: "transfer" | "scheduled_transfer" | "bill_payment" | "purchase";
  from: string;            // roommate_id
  to?: string;             // roommate_id, for transfers
  payee?: string;          // "Maple Court Apartments" | "Couch Co."
  amount: number;
  date: string;            // ISO date; future dates wait for /demo/advance
  status: "pending" | "done" | "failed";
  nessie_id?: string;
};
type Proposal = {
  id: string;  flow: "rent" | "front" | "purchase" | "utility";
  title: string;                                  // "Rent for December"
  legs: Leg[];
  required_approvers: string[];                   // roommate_ids
  approvals: Record<string, "pending" | "yes" | "no">;
  status: "pending" | "approved" | "executed" | "rejected" | "failed";
};
type TraceEvent = { ts: string; agent: "house" | "personal:alex" | "personal:sam" | "personal:jordan" | "treasurer" | "auditor" | "watcher"; event: string; detail: string };

type HouseState = {
  today: string;
  roommates: { id: string; name: string; balance: number; status: "ok" | "tight" | "no"; next_payday: string }[];
  owes: { from: string; to: string; amount: number; due: string }[];
  proposals: Proposal[];
  trace: TraceEvent[];   // newest first, max 50
};
type BankView = {
  bank_name: string; roommate_id: string; name: string; balance: number;
  transactions: { id: string; date: string; description: string; amount: number }[];  // newest first
  scheduled: { date: string; description: string; amount: number }[];
};
```

### Python module contracts (brain)

```python
# indicators.py [A]
compute(roommate_id) -> dict[str, {"value": float, "status": "good"|"watch"|"risk", "inputs": dict}]
# keys: the 8 workshop ones + runway_days, rent_to_income, days_to_payday, buffer_after(amount)

# tools.py [A]  (pure code, no LLM)
split_bill(bill_type, amount) -> {"shares": {roommate_id: float}}
can_cover(roommate_id, amount, date) -> {"level": "ok"|"tight"|"no", "earliest_date": str|None}
#   ok = balance stays >= $200 until next payday; tight = stays >= 0; no = goes negative
payday_plan(roommate_id, amount) -> {"fronter": roommate_id, "repay_date": str}
group_affordability(item, price, months_options=[1, 3]) -> {"answers": {rid: level}, "plan": {"months": int, "per_person_monthly": float}}

# nessie.py [D]  (live and mock implement the same class)
class NessieClient:
    balance(roommate_id) -> float
    transactions(roommate_id) -> list[dict]
    transfer(from_rid, to_rid, amount, description) -> str        # nessie_id
    pay_bill(rid, payee, amount, date) -> str
    purchase(rid, merchant, amount, description) -> str

# treasurer.py [D]
execute(proposal_id) -> list[Leg]   # raises unless proposal.status == "approved"; future-dated legs stay pending
run_due(today) -> list[Leg]         # called by /demo/advance

# proposals.py [B]
create(flow, title, legs, required_approvers) -> Proposal
record_reply(roommate_id, text) -> Proposal | None   # yes: yes|y|yep|ok|approve|👍 ; no: no|n|nah|cancel
#   applies to that roommate's oldest pending proposal; all yes -> status approved -> treasurer.execute

# auditor.py [B]
check(text, allowed_numbers: set[float], audience: "group"|roommate_id) -> {"ok": bool, "reasons": list[str]}
#   group messages may not contain any roommate's balance or income
```

**Contract additions (2026-11-08, from the foundation build)**

```python
# nessie.py
deposit(rid, amount, description) -> str     # /demo/advance credits every payday it crosses:
                                             # Alex 12-01, Sam 12-05, Jordan 12-15 (Jordan has $860 after repaying 12-16)
# tools.py
next_payday(rid, after) -> date | None       # first payday strictly after `after`
# can_cover: cash = balance - amount - legs already committed out of the account before next payday;
#            paydays on or before `date` count; ok >= 200, tight >= 0, no < 0;
#            earliest_date only set when level == "no"
# proposals.py
parse(text) -> "yes" | "no" | None           # used by /chat routing
# agents/personal.py
explain(rid, proposal) -> list[Reply]        # private DM about a proposal (Jordan's fronting DM)
# store (db.py)
roommates(); proposals(); bill(type); house_rule(type)
# NEW module M16 outbox.py   OUTBOX_MODE=stub|http
send(reply: Reply) -> None                   # http POSTs to gateway /send; treasurer confirmations
                                             # and /demo/trigger messages go through it
# contracts/models.py helper shapes
# Ask{amount, by_date, purpose}, Release{level, earliest_date}, SplitResult, PaydayPlan,
# Affordability{answers, plan|null}, AuditResult, LLMResult, BankTxn
```

**Behaviors pinned down**

- Rent with fronting is ONE proposal (flow `rent`, all 3 approve): Sam to Alex $800 now, Alex to Maple Court $2,400 now, Jordan to Alex $800 scheduled 2026-12-16.
- Couch: Alex buys $1,200 at Couch Co. now; Sam and Jordan each pay Alex $133.33, $133.33, $133.34 on 11-28, 12-28 and 01-28.
- The stub treasurer runs due legs through the stub Nessie and leaves future legs pending.
- Flags: every flag accepts `real`, mapping to sqlite / grok / live / http. Unbuilt modes (tiger, grok calls, live, photon) raise instead of falling back. `/health` returns `{ok, llm_mode, nessie_mode, modes: {...}}`.
- E2E: three tests (rent day, payday fronting, couch), each from `/demo/reset`; run all-stub, and all-real except NESSIE, LLM and OUTBOX.
- Sim REPL needs the brain on `OUTBOX_MODE=http`. Commands: `@alex <dm>`, `#group <text>`, `@sam #group <text>`, `/reset`, `/trigger rent_due`, `/advance YYYY-MM-DD`, `/state`.

## Workstream A (Teammate 2): data, indicators, demo clock

**Owns:** `config.py`, `db.py`, `seed.py`, `indicators.py`, `tools.py`, `demo.py`, `wellness/`. **Blocks:** everyone needs `db.py` and `seed.py` by hour 2.

- [ ] **A1. DB schema (by hour 1).** Tables (Postgres-compatible SQL so the same schema runs on SQLite and Tiger Data; on Tiger, make transactions a hypertable and add a monthly-spend continuous aggregate): `roommates`, `accounts`, `transactions`, `bills`, `house_rules`, `proposals`, `legs`, `approvals`, `trace`, `clock`. Helpers `get_roommate(rid)`, `get_by_handle(handle)`.
  - Done when: `python -m app.db --init` creates an empty DB and the tests pass.
- [ ] **A2. Seed (by hour 2).** Writes the 3 roommates with handles from `.env`, the starting balances, 3 months of history (paychecks on their schedule, rent share, groceries, 2 to 3 subscriptions, gig deposits for Jordan), the rent bill and the electric bill template. House rule: electric, Sam 40%.
  - Done when: `python -m app.seed` is repeatable and balances match the scenario table exactly.
- [ ] **A3. Demo clock.** `today()` reads the `clock` table; `set_today(date)`; reset sets it to 2026-11-28.
- [ ] **A4. Indicators.** Copy `wellness/` from the workshop repo. Build a profile adapter from our tables to the workshop's profile shape, then reuse `compute_metrics`. Add `runway_days`, `rent_to_income`, `days_to_payday`, `buffer_after(amount)`.
  - Done when: `compute("jordan")` returns all keys, and `runway_days` for Jordan is under 14.
- [ ] **A5. Tools.** `split_bill`, `can_cover`, `payday_plan` (fronter = the roommate with the highest `buffer_after(amount)`, repay = day after the debtor's next payday), `group_affordability` (try 1 month, then 3; pick the first plan where nobody is `no`).
  - Done when: every "expected results" bullet in the contracts section is a passing pytest.
- [ ] **A6. Demo endpoints logic.** `reset()`, `trigger(event)` (creates the rent or electric proposal through B's `proposals.create`, then pushes the house agent's message), `advance(to)` (sets the clock, calls `treasurer.run_due`).
- [ ] **A7 (P1). House rules from chat.** Parse "Sam pays 40% of electric" with Grok into a `house_rules` row, then ask the group to confirm.
- [ ] **A8 (P1). Receipt split.** `split_receipt(image)` using a Grok vision model for line items, then ask who shared which items.

## Workstream B (Teammate 3, except B3 and B6 for Teammate 2): agents, proposals, auditor, Grok

**Owns:** `main.py`, `agents/*`, `proposals.py`, `trace.py`. **Depends on:** A's tools (stub them with the expected results until A lands).

- [ ] **B1. `/chat` routing (by hour 2).** Look up the sender by handle. If the text parses as yes or no, call `proposals.record_reply` and return a confirmation. Otherwise send group messages to the house agent and DMs to that roommate's personal agent. Unknown handle: reply "I don't know you yet."
  - Done when: in mock mode, "yes" from all 3 on the rent proposal makes it `approved` and calls `treasurer.execute`.
- [ ] **B2. LLM adapter.** `GrokLLM` (OpenAI SDK, `base_url=https://api.x.ai/v1`, `GROK_MODEL`) with tool calling, and `MockLLM` that returns scripted replies for the 3 demo flows. Pick by `LLM_MODE`.
  - Done when: `LLM_MODE=grok` answers "what's my runway?" in a DM with a number taken from `indicators.compute`.
- [ ] **B3. Proposals state machine.** `create`, `record_reply`, `approve -> treasurer.execute`, `reject` (any "no" rejects and the house agent asks what to change). Write a trace event on each transition.
- [ ] **B4. House agent.** System prompt: the rules from the Agents section. Tools: `split_bill`, `group_affordability`, `payday_plan`, `ask_personal(rid, question)`, `create_proposal`. Handles the "rent\_due" trigger and free-form questions like "can we afford a $1,200 couch?"
  - Done when: the couch question produces trace events for 3 `ask_personal` calls and a 3-month purchase proposal.
- [ ] **B5. Personal agents.** P0: code decides the answer (`can_cover`), and the LLM only words the DM. They release to the house agent only `{level, earliest_date}`. In DMs, they answer the roommate's own questions with their own numbers.
  - Done when: Jordan gets a private DM explaining the fronting plan; the group sees only "Jordan can pay on the 16th."
- [ ] **B6. Auditor.** Before any reply is returned, check that every number is in `allowed_numbers` (gathered from the tool outputs of this turn). A group message may not contain any roommate's balance or income. On failure, retry once with the tool output in the prompt, then fall back to a template message.
  - Done when: a test that feeds the house agent a draft containing Jordan's $310 balance gets blocked.
- [ ] **B7. Trace.** `trace.log(agent, event, detail)` everywhere: asked, answered, proposed, approved, executed, blocked. `/state` returns the latest 50.
- [ ] **B8 (P1). Watcher.** On `trigger("watch")`, find anyone whose `can_cover` for their next due share is `tight` or `no`, and DM them first.

## Workstream C (Teammate 3): Photon gateway

**Owns:** `gateway/`. **Depends on:** only the `/chat` contract. Build against a fake brain that echoes until B lands.

- [ ] **C1. Sim mode (by hour 1).** `GATEWAY_MODE=sim`: a terminal REPL where you type `@alex yes` or `#group can we afford a couch?`. It posts `ChatIn` to the brain and prints the replies, labeled by target. This is how the whole team tests without phones.
  - Done when: rent day runs end to end in the terminal with the brain in mock mode.
- [ ] **C2. Photon hello world (by hour 1).** `spectrum-ts` cloud iMessage provider with `SPECTRUM_PROJECT_ID`/`SECRET`. Echo bot replies in a DM and in a test group chat that a teammate created and added the agent's number to.
- [ ] **C3. Photon mode.** `for await (const [space, message] of app.messages)`: ignore our own messages; build `ChatIn` (`chat_type` from whether the space is a group, `sender_handle` from the message sender); POST `/chat`; send each reply to the space mapped from its target. Use `space.responding(...)` to show typing while the brain works.
  - Done when: a real "yes" from each phone approves the rent proposal.
- [ ] **C4. Space registry.** Remember the group space on its first message, and each roommate's DM space when they text "hi". Persist it to a small JSON file so restarts don't lose it. `/health` shows what's registered.
- [ ] **C5. `POST /send`.** Lets the brain push proactive messages (rent due, executed, nudges) to the group or a DM.
- [ ] **C6. Dedupe and resilience.** Skip already-seen `message.id`s; retry a POST to the brain once; if the brain is down, reply "one sec, I'm restarting."
- [ ] **C7 (P1). Tapback approvals.** Turn a 👍 reaction on a proposal message into a "yes" (check the Photon docs for how reactions arrive).
- [ ] **C8 (P2). Voice nudge.** A Photon voice call to a roommate who hasn't approved rent by the deadline.

**Note:** reading Photon's group-chat and reactions pages is C's first 15 minutes. Our earlier summary didn't cover them.

**Photon 2.0 constraint (from their hackathon guide): iMessage group chats and calls need a dedicated iMessage line.** Standard hackathon lines may not get group chats. Plan:

1. **First 10 minutes:** sign up at photon.codes/beta (free, no promo code), create the project, add iMessage, then ask the Photon booth or Discord for a dedicated iMessage line for the demo.
2. **If no dedicated line: "house thread by relay."** Each roommate DMs the agent; the house agent posts every house message to all 3 DMs, prefixed "🏠 House:", and private personal-agent messages stay unprefixed. The dashboard shows the combined house thread. `Reply.target = {type: "group"}` is then implemented as a fan-out in the gateway, so no other code changes.
3. Optional: a Telegram or WhatsApp group through Photon as the real group, with iMessage DMs for the personal agents (shows "context across channels," which their judges value).

**Voice (separate $400 Best Voice Agent prize):** voice runs on a Photon SMS number with a Voice profile over SIP to Retell, ElevenLabs, LiveKit or Twilio. C8 becomes: the agent calls a roommate who hasn't approved rent, takes a spoken "yes" as the approval, and the conversation continues in text afterward with the call remembered. Keep it P2 unless the core is done by hour 14.

## Workstream D (Xander, except the dashboard and /state for Teammate 2): Nessie, treasurer, bank app, dashboard, Grok Bot

**Owns:** `nessie.py`, `treasurer.py`, `bank-app/`, `dashboard/`, `scripts/grok_seed.py`, `.github/workflows/`. **Depends on:** A's schema; `/state` and `/bank` shapes from the contracts.

- [ ] **D1. Mock Nessie (by hour 2).** `MockNessie` writes transfers, bills and purchases into our `transactions` table and updates balances. It's the default in `NESSIE_MODE=mock`.
- [ ] **D2. Live Nessie.** Read the Nessie docs and confirm endpoint names first. On `seed --nessie`: create 3 customers and checking accounts, store their ids on `roommates`, and deposit the starting balances. `transfer`, `pay_bill`, `purchase` map to the Nessie endpoints; `balance` and `transactions` read from Nessie.
  - Done when: one transfer in the Nessie API shows the new balance on `GET /bank/alex`.
- [ ] **D3. Treasurer.** `execute(proposal_id)`: refuses unless `approved`. Runs legs dated today or earlier and leaves future legs `pending`. Records `nessie_id`, sets proposal `executed` or `failed`, writes trace events, and asks the gateway to post a confirmation ("Rent sent: $2,400 to Maple Court Apartments"). `run_due(today)` runs pending legs whose date has passed.
  - Done when: rent day with Alex fronting Jordan creates Sam to Alex $800 now, the $2,400 landlord bill payment now, and Jordan to Alex $800 that runs only after `/demo/advance {to: "2026-12-16"}`.
- [ ] **D4. Brain read endpoints.** `GET /state` and `GET /bank/{rid}` exactly as in the contracts (coordinate with B on `main.py`).
- [ ] **D5. Bank app (Expo).** **Design replicates the Capital One mobile app look for the Capital One Nessie demo (team says Capital One approved this). Keep a visible "Demo: Nessie sandbox data" banner on every screen, no login or credential fields, and run it only through Expo Go (never publish to an app store or a public URL)**. Screens: roommate picker, then account (balance, scheduled payments, transactions newest first). Polls `/bank/{rid}` every 2 s; new transactions slide in and the balance animates. No login, no actions.
  - Done when: it runs in Expo Go on two phones over `--tunnel` and updates within 3 s of a "yes".
- [ ] **D6. House view dashboard (Next.js).** Three columns: roommates (balance, ok/tight/no, next payday) and who owes whom; proposals with an approval check per roommate; agent trace (newest first, colored by agent). Polls `/state` every 2 s. Hidden presenter buttons for `/demo/reset`, `trigger`, `advance`.
- [ ] **D7. Grok Bot GitHub Action.** `grok-review.yml` from the thread: on each PR, sends the diff to Grok and posts a summary plus a check for leaked keys and unapproved money moves. Add `XAI_API_KEY` as a repo secret.
- [ ] **D8. Write-up.** Devpost text including "How we used Cursor and Grok Bot", screenshots of Cursor and the Grok PR comments, a 2-minute backup video, and the raffle opt-in.

## One-shot the prototype, then add features

**Step 0 (one person, about 45 minutes):** create the repo, paste this whole doc into it as `SPEC.md`, copy `wellness/` from the PNC workshop repo into `brain/`, then give Cursor's agent this prompt:

```text
Read SPEC.md and REQUIREMENTS.md. The PNC workshop repo is at reference/pnc-workshop/ (read-only): search it
and reuse its wellness/ code, tests and sample data before writing anything new.
Build the House Rules skeleton exactly as the "Repo layout", "Shared contracts"
and Person A-D task lists describe, with ALL external services mocked:
every <MODULE>_MODE=stub and GATEWAY_MODE=sim.
First build the foundation commit exactly as REQUIREMENTS.md F1-F12 describes
(contracts/, fixtures/, stubs, registry, CI), then the P0 skeleton below on top of it.

Scope for this pass (P0 only):
- brain/: FastAPI app with every endpoint in the contracts, SQLite schema, seed matching the
  scenario table, demo clock, indicators (stub the workshop adapter if needed), tools with the
  exact expected results as pytest tests, proposals state machine, MockLLM with scripted replies,
  house + personal agents as plain functions, auditor, treasurer with MockNessie, trace.
- gateway/: sim mode REPL only ("@alex yes", "#group <text>") + POST /send that prints.
- dashboard/: Next.js page polling GET /state showing the three columns, unstyled is fine.
- bank-app/: Expo app with roommate picker + account screen polling GET /bank/{id}.

Acceptance test (make it pass, add it as brain/tests/test_e2e.py):
1. POST /demo/reset, then /demo/trigger {event:"rent_due"}.
2. Jordan's personal agent answers "no"; house agent proposes Alex fronts Jordan.
3. Replies "yes" from alex, sam, jordan via /chat approve it; treasurer executes.
4. /bank/alex shows +$800 from Sam and -$2,400 to Maple Court Apartments.
5. /demo/advance {to:"2026-12-16"} runs Jordan -> Alex $800.
6. #group "can we afford a $1,200 couch?" yields a 3-month plan; 3 yeses execute it.

Do not call any real API. Do not change the contracts. Keep functions small and typed.
```

**Step 1 (everyone):** pull the skeleton, run the e2e test and the sim REPL, and confirm rent day works on every laptop.

**Then swap mocks for real services, in this order.** Each item is its own branch and PR, so the Grok Bot reviews every one.

| # | Feature | Owner | Done when |
| --- | --- | --- | --- |
| 1 | Real Photon gateway (C2 to C5) | C | Rent day approved from 3 real phones |
| 2 | Real Nessie (D2) | D | Bank app balances come from Nessie |
| 3 | Grok for wording and tool calls (B2, B4) | B | Couch question answered by Grok with trace events |
| 4 | Workshop indicators wired in (A4) | A | Dashboard shows 12 indicators per roommate |
| 5 | Dashboard and bank app polish (D5, D6) | D | Updates visible within 3 s on the projector |
| 6 | Auditor hardened plus Grok Bot Action (B6, D7) | B, D | Leak test blocked; PR comments appear |
| 7 | P1 features: watcher, chat-set house rules, receipts, tapbacks | A, B, C | Each demoable alone |
| 8 | Freeze, rehearse, record backup video, Devpost | all | Hour 20 |

**Rule for every feature:** the e2e test must still pass with all mocks on before you merge.
