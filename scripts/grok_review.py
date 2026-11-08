"""Grok Bot PR review: send the PR diff to Grok, post a summary plus a risk check as a comment.

Runs in GitHub Actions. Skips (exit 0) when XAI_API_KEY is not configured.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request

MAX_DIFF_CHARS = 60_000
PROMPT = (
    "You review pull requests for House Rules, a roommate money agent. Reply in Markdown with:\n"
    "1. **Summary** (3 bullets max)\n"
    "2. **Risk check**: leaked API keys or secrets; money movement that skips an approval or "
    "bypasses the Treasurer; a roommate's balance, income or merchants reaching a group message; "
    "changes to contracts/ or fixtures/ without saying so. Say 'none found' for each clean item.\n"
    "Be brief."
)


def main() -> int:
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        print("XAI_API_KEY not configured; skipping Grok review.")
        return 0
    model = os.environ.get("GROK_MODEL", "").strip()
    if not model:
        print("GROK_MODEL repo variable is not set", file=sys.stderr)
        return 1
    base = os.environ["BASE_REF"]
    diff = subprocess.run(["git", "diff", f"origin/{base}...HEAD"], check=True,
                          capture_output=True, text=True).stdout
    truncated = len(diff) > MAX_DIFF_CHARS
    body = {"model": model, "messages": [
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": diff[:MAX_DIFF_CHARS] + ("\n[diff truncated]" if truncated else "")},
    ]}
    req = urllib.request.Request("https://api.x.ai/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        review = json.load(r)["choices"][0]["message"]["content"]
    comment = f"### Grok Bot review\n\n{review}\n\n_Automated review by Grok ({model})._"
    subprocess.run(["gh", "pr", "comment", os.environ["PR_NUMBER"], "--body", comment], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
