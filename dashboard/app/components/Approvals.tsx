"use client";
import type { Leg, Proposal } from "../../../contracts/types";
import { RuleSplit } from "./HouseRules";
import { Avatar, Empty, Status, money, shortDate } from "./ui";

const VOTE = {
  yes: { mark: "✓", cls: "bg-ok text-white" },
  no: { mark: "✕", cls: "bg-no text-white" },
  pending: { mark: "", cls: "bg-white text-slate ring-1 ring-hairline" },
} as const;

type Line = { text: string; status: Leg["status"] };

/** Legs as plain lines; installments between the same two people collapse into one line. */
function legLines(legs: Leg[], today: string, name: (id: string) => string): Line[] {
  const groups = new Map<string, Leg[]>();
  for (const leg of legs) {
    const k = `${leg.type === "scheduled_transfer" ? "transfer" : leg.type}|${leg.from}|${leg.to ?? leg.payee}`;
    groups.set(k, [...(groups.get(k) ?? []), leg]);
  }
  const when = (d: string) => (d <= today ? "now" : `on ${shortDate(d)}`);
  return [...groups.values()].map((g) => {
    const leg = g[0];
    const to = leg.to ? name(leg.to) : leg.payee ?? "someone";
    const verb = leg.type === "purchase" ? `${name(leg.from)} buys from ${to}`
      : leg.type === "bill_payment" ? `${name(leg.from)} pays ${to}`
      : `${name(leg.from)} sends ${to}`;
    const status = g.some((l) => l.status === "failed") ? "failed"
      : g.every((l) => l.status === "done") ? "done" : "pending";
    if (g.length === 1) return { text: `${verb}, ${money(leg.amount)} ${when(leg.date)}`, status };
    const total = Math.round(g.reduce((s, l) => s + l.amount, 0) * 100) / 100;
    const dates = g.map((l) => l.date).sort();
    if (dates[0] === dates[dates.length - 1]) return { text: `${verb}, ${money(total)} ${when(dates[0])}`, status };
    return {
      text: `${verb} ${money(total)} in ${g.length} payments, ${shortDate(dates[0])} to ${shortDate(dates[dates.length - 1])}`,
      status,
    };
  });
}

function Votes({ p, name }: { p: Proposal; name: (id: string) => string }) {
  return (
    <div className="flex items-center gap-3">
      {p.required_approvers.map((rid) => {
        const v = VOTE[p.approvals[rid] ?? "pending"];
        return (
          <span key={rid} className="relative" title={`${name(rid)}: ${p.approvals[rid] ?? "pending"}`}>
            <Avatar id={rid} name={name(rid)} size="sm" />
            <span className={`absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold ${v.cls}`}>
              {v.mark}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function ProposalRow({ p, today, name }: { p: Proposal; today: string; name: (id: string) => string }) {
  const waiting = p.required_approvers.filter((r) => (p.approvals[r] ?? "pending") === "pending").map(name);
  const total = p.legs.find((l) => l.type === "bill_payment" || l.type === "purchase")?.amount;
  return (
    <li className="animate-enter py-4 first:pt-0">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold leading-snug">{p.title}</div>
          <div className="text-sm text-slate">
            {p.status === "pending"
              ? waiting.length ? `Waiting on ${waiting.join(", ")}` : "Everyone said yes"
              : total !== undefined ? money(total) : p.flow === "rule" ? "No money moves" : ""}
          </div>
        </div>
        <Status status={p.status} />
      </div>
      <div className="mt-3"><Votes p={p} name={name} /></div>
      {p.rule && (
        <div className="mt-3">
          <RuleSplit rule={p.rule} ids={p.required_approvers} name={name} />
        </div>
      )}
      {p.legs.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-slate">
          {legLines(p.legs, today, name).map((l) => (
            <li key={l.text} className={l.status === "done" ? "text-ink" : ""}>
              <span className={`mr-2 inline-block h-1.5 w-1.5 rounded-full align-middle ${
                l.status === "done" ? "bg-ok" : l.status === "failed" ? "bg-no" : "bg-hairline"}`} />
              {l.text}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function Approvals({ proposals, today, name }: {
  proposals: Proposal[]; today: string; name: (id: string) => string;
}) {
  const open = proposals.filter((p) => p.status === "pending");
  const recent = proposals.filter((p) => p.status !== "pending").slice(-3).reverse();
  if (proposals.length === 0) {
    return <Empty>Nothing to approve. When someone proposes a bill, purchase or house rule, it shows up here.</Empty>;
  }
  return (
    <div>
      {open.length === 0 ? (
        <Empty>You're all caught up.</Empty>
      ) : (
        <ul className="divide-y divide-hairline">
          {[...open].reverse().map((p) => <ProposalRow key={p.id} p={p} today={today} name={name} />)}
        </ul>
      )}
      {recent.length > 0 && (
        <>
          <h3 className="mb-3 mt-6 text-sm font-medium text-slate">Earlier</h3>
          <ul className="divide-y divide-hairline opacity-80">
            {recent.map((p) => <ProposalRow key={p.id} p={p} today={today} name={name} />)}
          </ul>
        </>
      )}
    </div>
  );
}
