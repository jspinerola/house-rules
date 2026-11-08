# Harbor Bank - M13 bank app

Read-only Expo Go app: roommate picker, then an account screen (balance, scheduled payments,
transactions newest first) polling `GET /bank/{rid}` every 2 s. Fictional bank with Capital One-inspired
styling for the Nessie demo. No login or credential fields.

## Run on a phone

```bash
cd brain && ../.venv/bin/uvicorn app.main:app --port 8000     # stub brain
cd bank-app && npm i && npx expo start --tunnel ngrok           # scan the QR with Expo Go
```

The phone never talks to `localhost:8000`. Metro proxies `/brain/*` to `BRAIN_URL` (default
`http://localhost:8000`, see `metro.config.js`), and the app calls `https://<tunnel host>/brain/...`, so the
one Expo tunnel carries both the bundle and the API. LAN mode (`npx expo start`) works the same way.

- `--tunnel ngrok` uses the bundled `@expo/ngrok` dev dependency. Plain `--tunnel` on SDK 58 needs `npx expo login`.
- To skip the proxy, set `EXPO_PUBLIC_BRAIN_URL=https://your-brain-url` before `expo start`.

## Demo check (M13 done-when)

Open Xander in the app, then run:

```bash
bank-app/scripts/rent-demo.sh                 # reset, rent_due, yes x3
ADVANCE=1 bank-app/scripts/rent-demo.sh       # also advance to 2026-12-16
```

Within one poll (2 s) the balance tweens from $4,200 to $2,600, the Julian +$800 and Maple Court -$2,400 rows
slide in, and "From Kevin" appears under Scheduled. When you advance, it fades out of Scheduled and slides
into Transactions.

## Checks

```bash
npx tsc --noEmit && npx expo-doctor
```
