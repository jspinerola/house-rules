#!/usr/bin/env bash
# Drives the M13 check against the brain: reset, rent_due trigger, 3 yeses, then optional advance.
# Usage: scripts/rent-demo.sh [brain_url]   (default http://localhost:8000)
#        ADVANCE=1 scripts/rent-demo.sh     also runs /demo/advance to 2026-12-16
set -euo pipefail
B="${1:-${BRAIN_URL:-http://localhost:8000}}"
J='content-type: application/json'
post() { curl -sfS -X POST -H "$J" -d "$2" "$B$1"; echo; }

post /demo/reset '{}'
echo "Reset. Open Xander in the app, then press enter to trigger rent day."; read -r
post /demo/trigger '{"event":"rent_due"}'
for who in alex sam jordan; do
  post /chat "{\"chat_type\":\"group\",\"sender_handle\":\"sim:$who\",\"text\":\"yes\",\"message_id\":\"bank-$who-$RANDOM\",\"ts\":\"2026-11-28T09:00:00Z\"}" >/dev/null
  echo "$who: yes"
done
echo "Xander should now show \$2,600, +\$800 from Julian, -\$2,400 Maple Court, scheduled From Kevin."
if [[ "${ADVANCE:-0}" == 1 ]]; then
  echo "Press enter to advance to 2026-12-16 (scheduled -> transactions)."; read -r
  post /demo/advance '{"to":"2026-12-16"}'
fi
