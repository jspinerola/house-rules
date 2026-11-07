# House Rules

AI money manager that lives in your roommates' iMessage group chat.

House Rules splits bills by your house rules, times payments to each person's payday, answers "can we afford this as a group?" without anyone revealing their balance, and moves the money through the bank once the right people reply yes.

Unlike Splitwise-style apps that track IOUs, House Rules **actually moves money** (Nessie), checks financial health before asking anyone to pay (PNC), and needs **no app** — the group chat is the interface (Photon).

> Project status: in progress. Local mock mode is the default path; live Photon / Nessie / Grok wiring lands feature-by-feature.

## Demo household

Synthetic data only — a 3-bedroom apartment, **$2,400/mo** rent. Demo clock starts **2026-11-28**; rent is due **2026-12-01**.

| Roommate | Situation |
| --- | --- |
| **Alex** | Lease holder; landlord bill comes from Alex's account. Steady salary, paid on the 1st. |
| **Sam** | Works from home — house rule: Sam pays 40% of electric. Paid biweekly. |
| **Jordan** | Part-time plus gig income, paid on the 15th. Runway is tight at month start. |

### Core demo flows (P0)

1. **Rent day** — $800 each to Alex, then Alex pays the landlord. Everyone must approve.
2. **Payday fronting** — Jordan can't cover until the 15th; Alex fronts now, Jordan auto-repays after payday. Group never sees Jordan's balance.
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

## Setup (local / mock)

Prerequisites: Python 3.11+, Node 20 or Bun, pnpm (dashboard), Expo Go (bank app).

```bash
# once after clone — workshop reference (gitignored; not committed)
./scripts/setup_reference.sh

cp .env.example .env   # when available; start with mock modes

cd brain && pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --port 8000

cd gateway && npm i && GATEWAY_MODE=sim npm run dev

cd dashboard && pnpm i && pnpm dev

cd bank-app && npx expo start --tunnel
```

Default env for skeleton work:

| Key | Value |
| --- | --- |
| `LLM_MODE` | `mock` |
| `NESSIE_MODE` | `mock` |
| `GATEWAY_MODE` | `sim` |
| `DB_MODE` | `sqlite` |
| `BRAIN_URL` | `http://localhost:8000` |

Sim gateway REPL: type `@alex yes` or `#group can we afford a couch?` — posts to the brain and prints replies by target.

Acceptance path (once implemented): `POST /demo/reset` → trigger rent → three yeses → treasurer executes → `/demo/advance` for scheduled legs. See `brain/tests/test_e2e.py`.

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
