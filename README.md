# House Rules

AI money manager that lives in your roommates' iMessage group chat.

House Rules splits bills by your house rules, times payments to each person's payday, answers "can we afford this as a group?" without anyone revealing their balance, and moves the money through the bank once the right people reply yes.

Unlike Splitwise-style apps that track IOUs, House Rules **actually moves money** (Nessie), checks financial health before asking anyone to pay (PNC), and needs **no app** — the group chat is the interface (Photon).

> Project status: in progress. Local mock mode is the default path; live Photon / Nessie / Grok wiring lands feature-by-feature.

## Demo household

Synthetic data only — a 3-bedroom apartment, **$2,400/mo** rent. Demo clock starts **2026-11-28**; rent is due **2026-12-01**.

| Roommate | Situation |
| --- | --- |
| **Xander** | Lease holder; landlord bill comes from Xander's account. Steady salary, paid on the 1st. |
| **Julian** | Works from home — house rule: Julian pays 40% of electric. Paid biweekly. |
| **Kevin** | Part-time plus gig income, paid on the 15th. Runway is tight at month start. |

### Core demo flows (P0)

1. **Rent day** — $800 each to Xander, then Xander pays the landlord. Everyone must approve.
2. **Payday fronting** — Kevin can't cover until the 15th; Xander fronts now, Kevin auto-repays after payday. Group never sees Kevin's balance.
3. **Group affordability** — "Can we afford a $1,200 couch?" Personal agents answer ok / tight / no; house agent proposes a plan (e.g. $400 each over 3 months).

P1/P2 (utilities, receipts, watcher nudges, subscriptions, lease renewal) are documented in the build plan; they are not required for the first end-to-end demo.

## Architecture

Two services plus UIs:

| Part | Stack | Role |
| --- | --- | --- |
| **brain/** | Python 3.11, FastAPI, LangGraph, SQLite (Tiger Data later) | Agents, indicators, proposals, Nessie treasurer |
| **gateway/** | TypeScript (Node/Bun), spectrum-ts | Photon iMessage ↔ `POST /chat`; sim REPL for local demo |
| **dashboard/** | Next.js + Tailwind | House ledger, who owes what, agent trace |
| **bank-app/** | Expo (React Native) | Read-only "Harbor Bank" balances (proxied from brain) |

```
iMessage (Photon)  →  gateway  →  brain (/chat)
                                      ↓
                              house / personal agents
                                      ↓
                                   auditor
                                      ↓
                                 treasurer → Nessie
```

- **House agent** — group chat; shared bills and house rules only.
- **Personal agents** — one DM per roommate; only that roommate's accounts/indicators; release `ok` / `tight` / `no` (or a date).
- **Treasurer** — backend only; sole Nessie write access.
- **Auditor** — code (not LLM); blocks invented numbers, missing approvals, and anything a personal agent didn't release.

LLM: **Grok** via xAI's OpenAI-compatible API (`LLM_MODE=grok`), with `LLM_MODE=mock` for offline demos.

Bank: **Nessie** (`NESSIE_MODE=live|mock`). Balances on the ledger/bank app come from Nessie (or the mock that mirrors the same interface).

## Parallel work rules

1. **Contracts are frozen** — change an endpoint or JSON shape only after telling the team and updating docs first. See [AGENTS.md](./AGENTS.md).
2. **Every external service has a mock** — `LLM_MODE`, `NESSIE_MODE`, `GATEWAY_MODE=sim`. The demo must run with all three mocked.
3. **One demo clock** — brain has a fake "today"; only demo endpoints advance it so scheduled paybacks can be shown in seconds.

## Repo layout

```
house-rules/
  brain/                 FastAPI brain (port 8000)
  gateway/               Photon / sim gateway (port 8787)
  dashboard/             Next.js house view (port 3000)
  bank-app/              Expo Harbor Bank app
  scripts/               setup + Grok seed helpers
  .github/workflows/     Grok Bot PR review
  AGENTS.md              Guidance for coding agents
  SPEC.md                Full build plan (when present)
```

Folder owners and module contracts are in [AGENTS.md](./AGENTS.md).

## Setup (local, everything stubbed)

Prerequisites: Python 3.11, Node 20+ (npm), Expo Go for the bank app.

```bash
# once after clone: workshop reference (gitignored; not committed)
./scripts/setup_reference.sh
cp .env.example .env            # every <MODULE>_MODE=stub, GATEWAY_MODE=sim

cd brain && pip install -r requirements.txt     # also installs contracts/ (editable)
cd .. && pytest                                 # contract tests + expected.json + e2e

# terminal 1: brain (OUTBOX_MODE=http so proactive messages reach the sim gateway)
cd brain && OUTBOX_MODE=http uvicorn app.main:app --port 8000
# terminal 2: sim gateway REPL
cd gateway && npm i && npm run dev
# optional
cd dashboard && npm i && npm run dev            # http://localhost:3000
cd bank-app && npm i && npx expo start --tunnel ngrok   # phone reaches the brain via Metro's /brain proxy
```

Rent day in the sim REPL:

```text
/reset
/trigger rent_due
@alex yes
@sam yes
@jordan yes
/advance 2026-12-16
#group can we afford a $1,200 couch?
```

`@alex <text>` is a DM from Xander; `#group <text>` posts to the group as the last `@` sender (`@sam #group hi` to pick one).

### Photon mode (real phones)

The gateway talks to iMessage through Photon (`spectrum-ts`). On Photon's shared pool there are no group chats, so
`GATEWAY_FANOUT=1` relays every house message to all three DMs, prefixed "🏠 House:". Personal-agent replies stay
unprefixed and private.

1. In the Photon dashboard, add every roommate's phone number to the project. Numbers that aren't added can text
   in, but the agent can't text them back ("Target not allowed for this project"). Each person texts the Photon
   number they were given.
2. In `.env`: `GATEWAY_MODE=photon`, `GATEWAY_FANOUT=1`, `SPECTRUM_PROJECT_ID`, `SPECTRUM_PROJECT_SECRET`, and
   `ALEX_HANDLE` / `SAM_HANDLE` / `JORDAN_HANDLE` as `+1XXXXXXXXXX`.
3. Run it. If `uvicorn` isn't on your PATH, use `../.venv/bin/uvicorn`.

```bash
cd brain && uvicorn app.main:app --port 8000         # terminal 1; reads .env itself
curl -s -X POST localhost:8000/demo/reset            # after every brain restart (reseeds live Nessie)
cd gateway && npm run dev                            # terminal 2; reads ../.env
```

4. Each phone texts "hi". `curl -s localhost:8787/health` should list all three in `dms_registered`.

In a DM, start a message with `#house` to talk to the house agent (Grok picks the flow), e.g.
`#house rent's due soon` or `#house can we afford a $1,200 couch?`. Reply `yes` / `no` in your own DM to approve.
Anything else goes to your personal agent. Friends can watch their account live by opening the bank app in Expo Go
from the `npx expo start --tunnel ngrok` QR code.

### Module flags

Every module is reached through `brain/app/registry.py` and picks its implementation from `<MODULE>_MODE` (default `stub`): `DB_MODE` (`stub|sqlite|tiger`), `INDICATORS_MODE`, `TOOLS_MODE`, `PROPOSALS_MODE`, `AUDITOR_MODE`, `PERSONAL_MODE`, `HOUSE_MODE`, `TREASURER_MODE` (`stub|real`), `LLM_MODE` (`stub|grok`), `NESSIE_MODE` (`stub|live`), `OUTBOX_MODE` (`stub|http`), `GATEWAY_MODE` (`sim|photon`). `real` works for every flag. `tiger` raises until it is built. `GET /health` shows every module's mode.

`pytest` runs the e2e test twice: all stubs, and all real modules except Nessie, LLM and Outbox.

### Integration checkpoints (I1 / I4)

Flag flips from REQUIREMENTS.md. Report failures; do not patch other modules' code in a checkpoint run—flip the failing module back to `stub` on `main` and keep going.

| Checkpoint | Flags real | Proves |
| --- | --- | --- |
| **I1** (owned) | `DB_MODE=sqlite`, `INDICATORS_MODE=real`, `TOOLS_MODE=real` (all others stub) | Real numbers match `expected.json` |
| **I4** (partner) | I3 stack via `ALL_REAL` + `NESSIE_MODE=live` | Money moves in Nessie |

```bash
# I1 — default CI-safe (no live network)
./scripts/run_checkpoint.sh I1

# I4 — opt-in live Nessie (needs NESSIE_API_KEY in .env; HTTPS base URL)
NESSIE_LIVE_TEST=1 ./scripts/run_checkpoint.sh I4
```

The runner prints `CHECKPOINT I1|I4: PASS|FAIL`, a likely `module`, and the exact error. Bank app optional for I4 visual check: poll `/bank/{rid}` after rent execution.

## Tracks (hackathon context)

- **PNC 360° Financial Health Navigator** — per-roommate indicators + group affordability; code computes, LLM explains.
- **Photon** — product runs in iMessage (group + DMs + approvals).
- **Capital One Nessie** — real transfers, scheduled paybacks, bills, purchases.
- **SpaceXSI (Cursor + Grok Bot)** — built in Cursor; Grok powers product agents + PR review automation.
- **Tiger Data** — time-series balances/transactions (`DB_MODE=tiger` for demo; SQLite offline fallback).

## Credits

Financial wellness toolkit patterns (metrics, profile, forecast, tools registry, LangGraph flow, validation, LLM adapter) come from the [PNC UTD Hackathon 2026 workshop](https://github.com/devfulcrum/pnc-utd-hackathon-2026). Clone it into `reference/pnc-workshop` via `scripts/setup_reference.sh` and **reuse before rewriting**. Never edit `reference/`.

## Not financial advice

Demo uses synthetic data only. Indicators and agent answers are for a hackathon demo, not financial advice.
