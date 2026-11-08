# Extended feature: Telegram house group

Branch `telegram-group`. Gateway only: no changes to `brain/`, `contracts/` or `fixtures/`.

## Why

Photon's iMessage shared pool has no group chats. Until now, the house agent reached people by relaying "🏠 House:" copies into each roommate's iMessage DM. That put the house agent and each personal agent in **the same thread**, which reads as one bot talking to you and not as a household.

This feature gives each agent its own surface, matching the least-privilege split in `AGENTS.md`:

| Agent | Lives in | Sees |
| --- | --- | --- |
| House agent | **Telegram group** with all 3 roommates and the bot | Shared bills, house rules, ok/tight/no from personal agents |
| Personal agent (x3) | That roommate's **iMessage DM** through Photon | Only that roommate's accounts |

The brain already separates the two: every reply carries `target: group` or `target: dm`. The gateway decides where each one goes, with `group` going to the Telegram group and `dm` going to iMessage.

### Why not WhatsApp
Photon's WhatsApp Business provider is 1:1 only. Its space schema is just `{ id }`, with no group type. It also follows Meta's 24-hour rule: after 24 hours of silence, only pre-approved templates can be sent. Photon's Telegram provider supports real groups.

## How it works

```
Telegram group ── "rent's due soon" ──▶ gateway ──ChatIn{chat_type:"group", sender_handle:+1…}──▶ brain
                                           │                                                       │
Telegram group ◀── house reply ────────────┤◀── replies: [{target: group}, {target: dm, jordan}] ──┘
iMessage DM (Kevin) ◀── personal reply ───┘
```

### Inbound
- **One stream, both channels.** Spectrum runs the iMessage and Telegram providers side by side, so `app.messages` carries both. `message.platform` says which channel a message came from.
- **Group messages:**
  - The first group message from a known roommate registers that chat as the house group, stored as `tg:<chatId>` in `spaces.photon.json`.
  - Messages from any other group get one "This bot belongs to another house." and are ignored.
  - A Telegram sender maps to a roommate through `ALEX_TELEGRAM` / `SAM_TELEGRAM` / `JORDAN_TELEGRAM`. Each takes a numeric user id or `@username`, case-insensitive.
  - The brain sees the roommate's **phone handle** (`*_HANDLE`, defaulting to `sim:<id>`), so it's the same identity whether the message came from Telegram or iMessage.
  - Telegram message ids are only unique per chat, so they're namespaced as `tg:<chatId>:<messageId>` for dedupe.
- **Private chat with the bot** (chat id > 0): one reply, "I only work in the house group. Your private agent is in your iMessage DMs." Nothing goes to the brain.
- **Unknown sender in the group:** one reply per person, "I don't know @user yet (Telegram id N)…". This is how you find everyone's ids during setup. Nothing goes to the brain.

### Outbound
- **`target: group`**, including `POST /send` pushes like the rent-day trigger and "treasurer executed": goes to the Telegram group.
- **`target: dm`**: goes to that roommate's iMessage DM, same as before.
- **No group registered yet:** the iMessage relay ("🏠 House:" to all DMs, `#house` to talk to the house) still works as a fallback.
- **`GATEWAY_FANOUT=1` forces the relay** even when a group exists, so set it to `0` once the Telegram group is live.

### Unchanged
- Approvals: "yes" / "no" work in the group or in your iMessage DM.
- Typing indicators are best effort on both channels.
- Dedupe, the brain retry, and the "one sec." fallback.

## Setup (about 5 minutes)

1. **Create the bot.** In Telegram, message **@BotFather**:
   - Send `/newbot`, pick a name like "House Rules", and copy the **token**.
   - Send `/setprivacy`, pick your bot, choose **Disable**. Without this the bot only sees `/commands` in groups and never ordinary messages.
2. **Create the group.** Make a new Telegram group with all three roommates and add the bot.
3. **Fill in `.env`** at the repo root:
   ```bash
   TELEGRAM_BOT_TOKEN=123456:ABC...      # from BotFather; never commit, never logged
   GATEWAY_FANOUT=0                      # house messages go to the Telegram group, not DM copies
   ALEX_TELEGRAM=@alex_username          # or the numeric Telegram user id
   SAM_TELEGRAM=@sam_username
   JORDAN_TELEGRAM=@jordan_username
   # unchanged: ALEX_HANDLE / SAM_HANDLE / JORDAN_HANDLE phone numbers, SPECTRUM_* keys, GATEWAY_MODE=photon
   ```
   If you don't know usernames or ids, leave them empty. Start the gateway and have everyone say "hi" in the group: the bot replies with each person's Telegram id. Fill those in and restart the gateway.
4. **Run it:**
   ```bash
   cd brain && ../.venv/bin/uvicorn app.main:app --port 8000   # terminal 1
   curl -s -X POST localhost:8000/demo/reset                   # after every brain restart
   cd gateway && npm run dev                                   # terminal 2
   ```
   The gateway's startup line should end with `providers: imessage, telegram, house group: …`.
5. **Register:**
   - Each roommate texts "hi" to their Photon iMessage number, which registers their DM.
   - Someone says "hi" in the Telegram group, which registers the house group.
   - `curl -s localhost:8787/health` should then show `group_registered: true` and all three in `dms_registered`.

Telegram's webhook registers automatically through Photon, using the same `SPECTRUM_*` project credentials. If startup fails with a Telegram or webhook error, enable Telegram for the project in the Photon dashboard.

## Demo script

1. **Rent day, in the Telegram group:** "rent's due soon". You can also fire it from the terminal:
   ```bash
   curl -s -X POST localhost:8000/demo/trigger -H 'content-type: application/json' -d '{"event":"rent_due"}'
   ```
   - **Telegram group:** the house agent posts the rent split. It contains no balances, only who's ok and when.
   - **Kevin's iMessage:** the personal agent privately says Xander fronts Kevin's share until payday.
2. **Approve.** Everyone replies "yes", in the group or in their DM. The treasurer executes, and the group gets the confirmation.
3. **Payday:**
   ```bash
   curl -s -X POST localhost:8000/demo/advance -H 'content-type: application/json' -d '{"to":"2026-12-16"}'
   ```
   Kevin's $800 goes back to Xander.
4. **Couch, in the group:** "can we afford a $1,200 couch?" The house agent answers with a 3-month plan, and three yeses execute it.
5. **Bank app:** keep it open in a browser or Expo Go to show the money moving live.

Talking point: the house agent never sees anyone's balance. It asks each personal agent privately, and the personal agents answer only "ok", "tight", "no", or a date. Judges can see that split in the two different apps.

## Implementation notes

| File | Change |
| --- | --- |
| `gateway/src/photon.ts` | Spectrum starts with `imessage` plus `telegram` when `TELEGRAM_BOT_TOKEN` is set (`connect()`). New `handleTelegram()` handles group registration, sender mapping with `roommateFromTelegram()`, one-time hints and namespaced ids. Shared `respond()` gives best-effort typing on both channels. `getSpace` routes `tg:` ids to the Telegram provider. |
| `gateway/tests/telegram.test.ts` | 9 tests with a fake Spectrum stream mixing iMessage and Telegram messages, and a fake brain. |
| `.env.example` | `TELEGRAM_BOT_TOKEN`, `*_TELEGRAM`. |

Tests: gateway `npm run typecheck` is clean and `npm test` passes 21/21 (12 existing, 9 new). Root `pytest` is unchanged and green. No real Photon or Telegram calls are made in tests.

What the new tests cover:
- A group message reaches the brain as a group message with the roommate's phone handle.
- House replies go only to the group, and personal replies go to iMessage.
- `/send` group pushes land in the group.
- Mapping by `@username` works.
- An unknown sender gets one hint.
- A private chat gets pointed to iMessage.
- A second group is ignored.
- Ids are namespaced, and true duplicates are dropped.
- With no group yet, the iMessage relay is the fallback.

## Known limits
- **Julian's iMessage DMs** still need Julian's number added to the Photon project ("Target not allowed for this project"). Julian can take full part in the Telegram group in the meantime.
- **One house group per gateway.** To move to a different group, delete `group` from `gateway/spaces.photon.json` and restart.
- **Telegram tapback approvals** (👍 reactions) aren't wired up. That's C7 in SPEC, P1.
