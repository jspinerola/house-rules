# Demo day guide

How to run House Rules live for judges: what to start, what to say, and what to do when something goes wrong.

Everything runs live. Grok answers, Nessie moves the money, and Photon carries the chat: the house agent lives in the Telegram group, and each personal agent lives in its roommate's iMessage DMs. Stubs exist only for `pytest`.

## The cast

| Roommate | Id (in `.env`, never shown) | Plays |
| --- | --- | --- |
| Xander | `alex` | Has the most cash and the master bedroom; usually fronts |
| Julian | `sam` | Steady paycheck; fronts when Xander caps it |
| Kevin | `jordan` | $310 until payday on the 15th, plus gig income |

People see Xander, Julian and Kevin everywhere. The ids stay `alex` / `sam` / `jordan` in `.env` (`ALEX_TELEGRAM`, `ALEX_HANDLE`, ...), `spaces.photon.json` and the sim REPL.

## Before you start (once)

1. `.env` at the repo root has these modes:
   ```
   DB_MODE=real  LLM_MODE=grok  NESSIE_MODE=live  OUTBOX_MODE=http  GATEWAY_MODE=photon  GATEWAY_FANOUT=0
   ```
2. It also has these keys: `XAI_API_KEY`, `GROK_MODEL=grok-4.20-0309-non-reasoning`, `NESSIE_API_KEY`, `SPECTRUM_PROJECT_ID`, `SPECTRUM_PROJECT_SECRET` and `TELEGRAM_BOT_TOKEN`.
3. It also has these handles: `ALEX_TELEGRAM`, `SAM_TELEGRAM` and `JORDAN_TELEGRAM` (Telegram ids or @usernames), plus `ALEX_HANDLE`, `SAM_HANDLE` and `JORDAN_HANDLE` (iMessage phone numbers).
4. The bot is in the Telegram house group, and everyone has texted it once so their spaces are registered.
5. Optional: set `NEXT_PUBLIC_HOUSE_NAME` in `dashboard/.env.local` to your household's name. The default is "Maple Court".
6. Install dependencies once: `npm i` in `gateway/`, `dashboard/` and `bank-app/`.

### If a roommate isn't on Telegram

Play them from a terminal so the gateway never texts their real phone:

1. In `.env`, blank out that roommate's `*_HANDLE`. For Kevin, that's `JORDAN_HANDLE=`.
2. In `gateway/spaces.photon.json`, remove their line under `dms`. Keep a copy so you can restore it afterwards.
3. Run the sim (step 5 below) and type as them: `@jordan #group yes` for the group, `@jordan <text>` for their DM.

Their group messages and the house's replies to them show only in the sim terminal. Their private DMs aren't delivered anywhere; the dashboard says one was sent.

## Start the stack

Use one terminal each, in this order.

```bash
# 1. Brain (port 8000). With live Nessie it reseeds on startup, so it always starts clean.
cd brain && ../.venv/bin/uvicorn app.main:app --port 8000

# 2. Gateway (port 8787): Telegram group + iMessage DMs
cd gateway && npm run dev

# 3. Dashboard (port 3000), for the projector
cd dashboard && npm run dev

# 4. Bank app: scan the QR code with Expo Go (Camera app on iPhone)
cd bank-app && npx expo start --tunnel ngrok

# 5. Only if someone plays a roommate from a terminal (port 8788)
cd gateway && GATEWAY_MODE=sim GATEWAY_PORT=8788 npm run dev
```

Check that everything is up:

```bash
curl -s localhost:8000/health   # llm_mode "grok", nessie_mode "live"
curl -s localhost:8787/health   # mode "photon", house group registered
```

Right before you present, start from a clean slate:

```bash
curl -X POST localhost:8000/demo/reset
```

This reseeds the Nessie accounts and sets the date to Nov 28. It also clears every house rule except the seeded electric one, plus all preferences and proposals.

## On screen

- **Projector:** `localhost:3000`. Press `d` to show the presenter controls: Start over, Rent is due, Electric bill, Jump to Dec 16. Press `d` again to hide them. The status line should say "All services live".
- **Phones:** Expo Go shows each roommate's account: balance, scheduled payments, transactions and "What your agent knows".
- **Chat:** the Telegram group and each person's iMessage DMs.

## The script

Say these lines as written. Group messages go in the Telegram group, and DMs go in that person's iMessage chat with their agent.

### 1. A house rule, set in chat

| Who | Where | Message |
| --- | --- | --- |
| Xander | Group | `xander has the master bedroom so rent should be 40/30/30` |
| | | The house previews **Xander $960, Julian $720, Kevin $720** and asks everyone for a yes |
| Xander, Julian, Kevin | Group | `yes` (or 👍 sent as its own message) |

The rule appears on the dashboard's **House rules** card. No money moves.

Talking point: rules need everyone's yes. A personal agent can't set one; asking in a DM gets "say it in the group".

### 2. A private preference changes the plan

| Who | Where | Message |
| --- | --- | --- |
| Xander | DM | `don't make me front more than $500 at a time` |

Talking point: it's private. The group never learns the cap, only who ends up fronting.

### 3. Rent day

| Who | Where | Message |
| --- | --- | --- |
| Xander | Group | `ok lets do rent` (or press **Rent is due** on the presenter bar) |

The plan: Julian sends his $720, Xander pays Maple Court $2,400, and **Julian fronts Kevin's $720** because Xander capped fronting at $500. Kevin auto-repays on Dec 16.

Kevin's DM explains why, using only his own numbers: his $310 doesn't cover the $720 before his payday. Julian's DM asks him to agree to front. The group sees only ok, tight or no.

| Who | Where | Message |
| --- | --- | --- |
| Xander, Julian, Kevin | Group | `yes` |

The treasurer moves the money through Nessie and confirms in the group. Balances change in the bank app and on the dashboard, and the circle draws "Kevin owes Julian $720 by Dec 16".

### 4. A purchase

| Who | Where | Message |
| --- | --- | --- |
| Julian | Group | `what if xander paid half of a 1200 couch since it's going in his room?` |
| Xander | Group | `lets do that` |
| Everyone | Group | `yes` |

The plan comes out to Xander $200/mo, Julian $100/mo and Kevin $100/mo over 3 months. Kevin is tight, so the house spreads it out rather than asking for cash up front.

### 5. Ask your agent anything

| Who | Where | Message |
| --- | --- | --- |
| Kevin | DM | `why am i tight right now?` |
| Kevin | DM | `can i afford a 100 dinner this week?` |
| Julian | DM | `im saving for japan, keep at least $1,000 in my checking` |

Answers come from that person's real history: subscriptions renewing before payday, gig income (never counted as guaranteed), and their cushion.

### 6. Payday

Press **Jump to Dec 16** (or `curl -X POST localhost:8000/demo/advance -H 'content-type: application/json' -d '{"to":"2026-12-16"}'`).

Paydays land, Kevin's scheduled $720 goes back to Julian, and the thread disappears from the circle. Indicators in the bank app move because the money moved.

## Things to know while presenting

- **"yes" approves the oldest open proposal for that person.** The house never asks yes/no questions, so a stray "yes" can't approve the wrong thing.
- **👍 counts only as a message.** Reacting to a message with 👍 is ignored; the gateway forwards text only.
- **Rules go in the group, not in a DM.**
- **Rent rolls forward.** After December is paid, the next rent proposal is for January.
- **The dashboard is safe to project.** It never shows DM content or blocked figures; the activity feed only says a private message was sent.
- **Restarting the brain starts the demo over.** With live Nessie it reseeds on startup.

## When something goes wrong

| What you see | Cause | Fix |
| --- | --- | --- |
| Gateway: `EADDRINUSE :8787` | Another gateway (or a sim without `GATEWAY_PORT=8788`) is still running | `ss -ltnp \| grep 8787`, then stop that process |
| Dashboard says "Can't reach the house server" | The brain isn't running or crashed | Start the brain (step 1) |
| Old names (Alex, Sam, Jordan) show up | Old code or old data | Restart everything, then `POST /demo/reset`; reload Expo Go |
| A reply seems generic or slow | Grok timed out (8 s) and the agent used its backup wording | Say it again |
| Activity says the auditor held back a reply | A draft had a number no tool produced, or a private figure | Expected; the safe version was sent instead |
| "Nobody could front a share" | Everyone's front cap is below the share | DM a higher cap ("I can front up to $1,000"), then `lets do rent` again |
| A roommate isn't recognized in Telegram | Their id isn't in `*_TELEGRAM` | Add it to `.env` and restart the gateway |

## Afterwards

- Restore any `*_HANDLE` you blanked and the `dms` entries in `gateway/spaces.photon.json`.
- Stop every terminal (Ctrl+C), including Expo; its ngrok tunnel stops with it.
