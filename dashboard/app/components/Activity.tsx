"use client";
import { useEffect, useRef, type ReactNode } from "react";
import type { Proposal, TraceEvent } from "../../../contracts/types";
import { traceKey } from "../lib/brain";
import { Avatar, Empty, money, shortDate } from "./ui";

type Item = { key: string; ts: string; who: ReactNode; text: ReactNode; quote?: string };
type Ctx = { name: (id: string) => string; title: (pid: string) => string };

const ISO = /\b(\d{4}-\d{2}-\d{2})\b/g;
const dates = (s: string) => s.replace(ISO, (_, d: string) => shortDate(d));
const LEVEL_WORD: Record<string, string> = { ok: "on track", tight: "tight", no: "short" };
const TRIGGER: Record<string, string> = { rent_due: "Rent is due", electric_bill: "The electric bill arrived", watch: "Checking upcoming bills" };

function Glyph({ label, cls }: { label: string; cls: string }) {
  return (
    <span aria-hidden className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

const HOUSE = (
  <span aria-hidden className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-ink">
    <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="white" strokeWidth="1.6" strokeLinejoin="round">
      <path d="M2.5 7.5 8 3l5.5 4.5V13h-3.5V9.5h-4V13H2.5z" />
    </svg>
  </span>
);
const TREASURER = <Glyph label="$" cls="bg-ok/12 text-ok" />;
const AUDITOR = <Glyph label="✓" cls="bg-mist text-slate" />;

function who(agent: TraceEvent["agent"], ctx: Ctx): ReactNode {
  if (agent === "house" || agent === "watcher") return HOUSE;
  if (agent === "treasurer") return TREASURER;
  if (agent === "auditor") return AUDITOR;
  const rid = agent.replace("personal:", "");
  return <Avatar id={rid} name={ctx.name(rid)} size="sm" />;
}

const PAYMENT = /^p\d+ (\w+) (.+?) to (.+?) \$([\d,]+(?:\.\d+)?)/;

/** One trace event as a plain sentence, or null for internal steps that don't help a viewer. */
function describe(e: TraceEvent, ctx: Ctx): Omit<Item, "key" | "ts" | "who"> | null {
  const rid = e.agent.startsWith("personal:") ? e.agent.slice(9) : "";
  const agentName = rid ? `${ctx.name(rid)}'s agent` : "";
  switch (e.event) {
    case "replied":
      if (e.detail.startsWith("to group: ")) return { text: "House", quote: e.detail.slice(10) };
      // Private DMs stay private: say that one was sent, never what it said.
      return { text: `${agentName || "House"} messaged ${ctx.name(e.detail.slice(3).split(":")[0])} privately` };
    case "triggered":
      return { text: TRIGGER[e.detail] ?? "Something came up" };
    case "proposed": {
      const m = /^p\d+ (.+?): \d+ legs/.exec(e.detail);
      return { text: <>Proposed <b className="font-semibold">{m?.[1] ?? "a plan"}</b></> };
    }
    case "approved":
      if (rid) return { text: <>{ctx.name(rid)} approved {ctx.title(e.detail)}</> };
      return { text: <>Everyone approved <b className="font-semibold">{e.detail.replace(/^p\d+ /, "").split(":")[0]}</b></> };
    case "declined":
      return { text: `${ctx.name(rid)} declined ${ctx.title(e.detail)}` };
    case "rejected":
      return { text: `${e.detail.replace(/^p\d+ /, "").split(":")[0]} was declined` };
    case "answered": {
      const level = /:\s*(ok|tight|no)/.exec(e.detail)?.[1] ?? "";
      const date = /can pay (\d{4}-\d{2}-\d{2})/.exec(e.detail)?.[1];
      return { text: `${agentName} said ${LEVEL_WORD[level] ?? "it checked privately"}${date ? ` until ${shortDate(date)}` : ""}` };
    }
    case "executed": {
      const m = PAYMENT.exec(e.detail);
      if (!m) return { text: "Moved money" };
      const [, type, from, to, amt] = m;
      const amount = money(Number(amt.replace(/,/g, "")));
      if (type === "bill_payment") return { text: `${from} paid ${to} ${amount}` };
      if (type === "purchase") return { text: `${from} bought from ${to}, ${amount}` };
      return { text: `${from} sent ${to} ${amount}` };
    }
    case "failed":
      return { text: "A payment didn't go through. The treasurer is reporting back." };
    case "rule_saved":
      return { text: <>New house rule: <b className="font-semibold">{e.detail.split(":")[0]}</b></> };
    case "rule_removed":
      return { text: `${e.detail.split(":")[0]} is back to an even split` };
    case "preference_set":
      return { text: `${agentName} saved a private preference` };
    case "blocked":
      return { text: "Auditor held back a reply until its numbers checked out" };
    case "no_fronter":
      return { text: "Nobody could front a share, so the bill is on hold" };
    case "clock":
      return { text: `Calendar moved ahead: ${dates(e.detail.replace(/^.*-> /, ""))}` };
    default:
      return null; // tool calls, routing, retries: internal
  }
}

export function Activity({ trace, proposals, name }: {
  trace: TraceEvent[]; proposals: Proposal[]; name: (id: string) => string;
}) {
  const titles = new Map(proposals.map((p) => [p.id, p.title]));
  const ctx: Ctx = { name, title: (pid) => titles.get(pid) ?? "the plan" };
  const items: Item[] = trace.flatMap((e) => {
    const d = describe(e, ctx);
    return d ? [{ key: traceKey(e), ts: e.ts, who: who(e.agent, ctx), ...d }] : [];
  }).slice(0, 30);

  // Items already shown; null until first render so the initial load doesn't animate.
  const seen = useRef<Set<string> | null>(null);
  useEffect(() => { seen.current = new Set(items.map((i) => i.key)); });
  const fresh = (k: string) => seen.current !== null && !seen.current.has(k);

  if (items.length === 0) return <Empty>Quiet for now. Messages, approvals and payments show up here as they happen.</Empty>;
  return (
    <ol className="space-y-3.5">
      {items.map((i) => (
        <li key={i.key} className={`flex gap-3 ${fresh(i.key) ? "animate-enter" : ""}`}>
          {i.who}
          <div className="min-w-0 flex-1 pt-0.5">
            {i.quote ? (
              <p className="rounded-2xl rounded-tl-md bg-mist px-3.5 py-2 text-[0.95rem] leading-snug">{i.quote}</p>
            ) : (
              <p className="text-[0.95rem] leading-snug">{i.text}</p>
            )}
            <time className="mt-0.5 block text-xs text-slate">
              {new Date(i.ts).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
            </time>
          </div>
        </li>
      ))}
    </ol>
  );
}
