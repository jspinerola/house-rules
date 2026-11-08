# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.45"]
# ///
"""Demo director: plays the House Rules demo against a running brain and records it.

    uv run --with playwright playwright install ffmpeg   # once: Playwright's video encoder
    uv run scripts/record_demo.py                 # drive the demo + record dashboard and bank app
    uv run scripts/record_demo.py --watch 240     # only record (people type in the real chats)

What it does, in drive mode:
  1. POST /demo/reset, then opens the dashboard (1920x1080) and the bank app as Kevin and Julian
     (phone-sized), each recorded to its own video.
  2. Plays every beat from DEMO_DAY_GUIDE.md by posting each roommate's message to POST /chat,
     pausing between beats so viewers can follow.
  3. Relays the agents' replies to the gateway (POST /send) when it's running, so the house's
     messages land in the Telegram group and each personal agent's DM lands on that phone.
     Roommates' own messages can't be posted as them (bots can't impersonate users), so they
     appear only on the dashboard and in captions.srt.
  4. Writes timeline.txt and captions.srt next to the videos for editing.

Handles: <ID>_HANDLE from the environment, then the repo .env, then sim:<id>. URLs come from
--brain / --dashboard / --bank or BRAIN_URL / GATEWAY_URL. Browser: system Chromium by default
(--chromium PATH); run `uv run --with playwright playwright install chromium` to use Playwright's own.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {"alex": "Xander", "sam": "Julian", "jordan": "Kevin"}


# ---------- the script ----------

@dataclass
class Say:
    who: str          # roommate id
    where: str        # "group" | "dm"
    text: str
    hold: float = 4.0  # seconds to leave on screen after the reply arrives


@dataclass
class Act:
    label: str
    path: str
    body: dict | None = None
    hold: float = 5.0


@dataclass
class Beat:
    title: str
    steps: list = field(default_factory=list)
    expect: str = ""   # a check on /state after the beat, see check()


def yeses(*who: str, hold: float = 2.5) -> list[Say]:
    return [Say(w, "group", "yes", hold) for w in who]


BEATS = [
    Beat("A house rule, set in chat", [
        Say("alex", "group", "xander has the master bedroom so rent should be 40/30/30", 6),
        *yeses("alex", "sam", "jordan"),
    ], expect="rent_rule"),
    Beat("A private preference", [
        Say("alex", "dm", "don't make me front more than $500 at a time", 5),
    ], expect="front_cap"),
    Beat("Rent day", [
        Say("alex", "group", "ok lets do rent", 8),
        *yeses("alex", "sam", "jordan", hold=3),
    ], expect="rent_paid"),
    Beat("A shared purchase", [
        Say("sam", "group", "can we get a 1200 couch? xander pays half since it's going in his room", 7),
        *yeses("alex", "sam", "jordan", hold=3),
    ], expect="couch"),
    Beat("Ask your agent anything", [
        Say("jordan", "dm", "can i afford a 100 dinner this week?", 6),
    ]),
    Beat("Payday", [
        Act("Jump to Dec 16", "/demo/advance", {"to": "2026-12-16"}, 7),
    ], expect="repaid"),
]


# ---------- plumbing ----------

def dotenv() -> dict[str, str]:
    out: dict[str, str] = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def http(method: str, url: str, body: dict | None = None, timeout: float = 60) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status < 500
    except (urllib.error.URLError, OSError):
        return False


class Clock:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.lines: list[str] = []
        self.captions: list[tuple[float, float, str]] = []

    def now(self) -> float:
        return time.monotonic() - self.t0

    def mark(self, text: str) -> None:
        line = f"{fmt(self.now())}  {text}"
        self.lines.append(line)
        print(line, flush=True)

    def caption(self, start: float, end: float, text: str) -> None:
        self.captions.append((start, end, text))


def fmt(s: float) -> str:
    return f"{int(s // 60):02d}:{s % 60:05.2f}"


def srt_time(s: float) -> str:
    ms = int(round(s * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def check(kind: str, state: dict) -> str | None:
    """None if the beat landed, else what to look at. Grok wording varies; the state shouldn't."""
    rules = {r["bill_type"]: r for r in state.get("rules", [])}
    props = state.get("proposals", [])
    if kind == "rent_rule":
        return None if "rent" in rules else "no rent rule saved (did the vote open and get 3 yeses?)"
    if kind == "rent_paid":
        return None if any(p["flow"] == "rent" and p["status"] == "executed" for p in props) else "rent not executed"
    if kind == "couch":
        return None if any(p["flow"] == "purchase" for p in props) else "no couch proposal"
    if kind == "repaid":
        return None if state.get("today") == "2026-12-16" else "clock did not move"
    return None


# ---------- run ----------

def drive(args, handles: dict[str, str], clock: Clock, problems: list[str]) -> None:
    relay = args.gateway and reachable(f"{args.gateway}/health")
    clock.mark(f"relay to gateway: {'on' if relay else 'off'}")
    for beat in BEATS:
        clock.mark(f"== {beat.title}")
        for step in beat.steps:
            if isinstance(step, Act):
                start = clock.now()
                out = http("POST", f"{args.brain}{step.path}", step.body)
                clock.mark(f"[presenter] {step.label}: {json.dumps(out)[:80]}")
                clock.caption(start, start + step.hold, step.label)
                time.sleep(step.hold * args.pace)
                continue
            start = clock.now()
            who = NAMES.get(step.who, step.who)
            where = "the group" if step.where == "group" else "their DM"
            clock.mark(f"{who} ({step.where}): {step.text}")
            msg = {"chat_type": step.where, "sender_handle": handles[step.who], "text": step.text,
                   "message_id": f"director-{int(time.time() * 1000)}", "ts": datetime.now().isoformat()}
            out = http("POST", f"{args.brain}/chat", msg, timeout=90)
            for reply in out.get("replies", []):
                t = reply["target"]
                dest = "group" if t["type"] == "group" else f"dm:{t['roommate_id']}"
                clock.mark(f"   -> [{dest}] {reply['text'][:110]}")
                if relay:
                    try:
                        http("POST", f"{args.gateway}/send", reply, timeout=15)
                    except (urllib.error.URLError, OSError) as e:
                        problems.append(f"relay failed for {dest}: {e}")
            clock.caption(start, start + step.hold * args.pace, f"{who} in {where}: “{step.text}”")
            time.sleep(step.hold * args.pace)
        if beat.expect:
            issue = check(beat.expect, http("GET", f"{args.brain}/state"))
            if issue:
                problems.append(f"{beat.title}: {issue}")
                clock.mark(f"   !! {issue}")


def main() -> int:
    env = dotenv()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brain", default=os.environ.get("BRAIN_URL") or env.get("BRAIN_URL") or "http://localhost:8000")
    p.add_argument("--gateway", default=os.environ.get("GATEWAY_URL") or env.get("GATEWAY_URL") or "http://localhost:8787",
                   help="relay agent replies to the real chats; pass '' to disable")
    p.add_argument("--dashboard", default="http://localhost:3000")
    p.add_argument("--bank", default="http://localhost:8081", help="bank app web (expo start --web); '' to skip")
    p.add_argument("--out", default=str(ROOT / "recordings" / datetime.now().strftime("%Y%m%d-%H%M%S")))
    p.add_argument("--pace", type=float, default=1.0, help="multiply every pause (1.5 = slower)")
    p.add_argument("--watch", type=float, metavar="SECONDS", help="record only, for this long; don't drive")
    p.add_argument("--no-reset", action="store_true", help="don't POST /demo/reset first")
    p.add_argument("--chromium", default=shutil.which("chromium") or shutil.which("chromium-browser") or "",
                   help="browser binary; empty = Playwright's bundled Chromium")
    args = p.parse_args()

    if not reachable(f"{args.brain}/health"):
        print(f"brain not reachable at {args.brain}; start it first (see DEMO_DAY_GUIDE.md)", file=sys.stderr)
        return 1
    if not reachable(args.dashboard):
        print(f"dashboard not reachable at {args.dashboard}; start it first", file=sys.stderr)
        return 1
    bank = args.bank if args.bank and reachable(args.bank) else ""
    if args.bank and not bank:
        print(f"bank app not reachable at {args.bank}; recording the dashboard only "
              "(start it with: cd bank-app && npx expo start --web)", file=sys.stderr)
    handles = {rid: os.environ.get(f"{rid.upper()}_HANDLE") or env.get(f"{rid.upper()}_HANDLE") or f"sim:{rid}"
               for rid in NAMES}

    from playwright.sync_api import sync_playwright  # imported late so --help works without it

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.watch and not args.no_reset:
        http("POST", f"{args.brain}/demo/reset", timeout=120)

    problems: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium or None, headless=True)
        views = [("dashboard", args.dashboard, {"width": 1920, "height": 1080}, None)]
        if bank:
            views += [(f"bank-{NAMES[r].lower()}", bank, {"width": 430, "height": 932}, NAMES[r])
                      for r in ("jordan", "sam")]
        contexts = []
        for name, url, size, pick in views:
            ctx = browser.new_context(viewport=size, device_scale_factor=1,
                                      record_video_dir=str(out / f".{name}"), record_video_size=size)
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle")
            if pick:  # the bank app opens on a roommate picker
                page.get_by_text(pick, exact=True).first.click()
            contexts.append((name, ctx, page))

        clock = Clock()
        time.sleep(3)  # let the dashboard's load-in finish before the first beat
        clock.mark("recording started")
        try:
            if args.watch:
                clock.mark(f"watching for {args.watch:g}s; type in the real chats now")
                time.sleep(args.watch)
            else:
                drive(args, handles, clock, problems)
            time.sleep(4)
            clock.mark("done")
        finally:
            for name, ctx, page in contexts:
                video = page.video
                ctx.close()
                if video:
                    target = out / f"{name}.webm"
                    Path(video.path()).replace(target)
                    shutil.rmtree(out / f".{name}", ignore_errors=True)
            browser.close()

    (out / "timeline.txt").write_text("\n".join(clock.lines) + "\n")
    (out / "captions.srt").write_text("".join(
        f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{text}\n\n" for i, (a, b, text) in enumerate(clock.captions, 1)))
    print(f"\nsaved to {out}:")
    for f in sorted(out.iterdir()):
        print(f"  {f.name}")
    if problems:
        print("\nthings to check before using this take:")
        for prob in problems:
            print(f"  - {prob}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
