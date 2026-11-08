"""Grok Bot PR review: send the PR diff to Grok, post a summary plus risk flags as a comment.

Runs in GitHub Actions. Skips (exit 0) when XAI_API_KEY is not configured.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4.7"
MAX_DIFF_CHARS = 60_000
PROMPT = (
    "You review pull requests for House Rules, a roommate money agent. Reply in Markdown with "
    "exactly these two sections and nothing else:\n"
    "**Summary**: exactly 3 bullets describing what the diff changes.\n"
    "**Flags**: exactly 3 bullets, one per check below. Each says 'none found' or cites file:line "
    "with a short reason.\n"
    "- Leaked keys: API keys, tokens, passwords or other secrets added to the code.\n"
    "- Hardcoded balances: roommate balances, incomes or merchants hardcoded in app code or "
    "reaching a group message (fixtures/ and tests/ are expected to hold seed numbers).\n"
    "- Money without approval: money movement (transfer, bill payment, purchase, Nessie write) "
    "that skips the approval check or bypasses the Treasurer.\n"
    "Be brief."
)


def main() -> int:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("XAI_API_KEY not configured; skipping Grok review.")
        return 0
    model = os.environ.get("GROK_MODEL", "").strip() or DEFAULT_MODEL
    base = os.environ["BASE_REF"]
    diff = subprocess.run(["git", "diff", f"origin/{base}...HEAD"], check=True,
                          capture_output=True, text=True).stdout
    truncated = len(diff) > MAX_DIFF_CHARS
    body = {"model": model, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": diff[:MAX_DIFF_CHARS] + ("\n[diff truncated]" if truncated else "")},
    ]}
    req = urllib.request.Request(XAI_URL, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            review = json.load(r)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print(f"xAI request failed ({e.code}, model={model}): {e.read().decode(errors='replace')}",
              file=sys.stderr)
        return 1
    comment = f"### Grok Bot review\n\n{review}\n\n_Automated review by Grok ({model})._"
    if os.environ.get("DRY_RUN"):
        print(comment)
        return 0
    # One bot comment per PR, updated on each push.
    subprocess.run(["gh", "pr", "comment", os.environ["PR_NUMBER"], "--body", comment,
                    "--edit-last", "--create-if-none"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
