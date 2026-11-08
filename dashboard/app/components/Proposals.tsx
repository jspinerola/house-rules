"use client";
import type { Leg, Proposal } from "../../../contracts/types";
import { money } from "../lib/brain";
import { Empty, Panel, StatusBadge } from "./ui";

const VOTE = {
  yes: { mark: "✓", cls: "bg-ok/15 text-ok ring-ok/60" },
  pending: { mark: "…", cls: "bg-panel-2 text-fog ring-line" },
  no: { mark: "✗", cls: "bg-no/15 text-no ring-no/60" },
} as const;

const LEG_STATUS: Record<Leg["status"], string> = {
  pending: "text-tight",
  done: "text-ok",
  failed: "text-no",
};

const LEG_TYPE: Record<Leg["type"], string> = {
  transfer: "transfer",
  scheduled_transfer: "scheduled",
  bill_payment: "bill",
  purchase: "purchase",
};

function LegRow({ leg, today, name }: { leg: Leg; today: string; name: (id: string) => string }) {
  const dest = leg.to ? name(leg.to) : leg.payee ?? "?";
  const scheduled = leg.type === "scheduled_transfer" || leg.date > today;
  return (
    <li className="border-t border-line/60 py-2.5 first:border-t-0">
      <div className="flex items-center gap-2 font-mono text-sm uppercase tracking-wider">
        <span className="text-fog">{LEG_TYPE[leg.type]}</span>
        {scheduled && (
          <span className="rounded-md bg-house/15 px-2 py-0.5 normal-case text-house ring-1 ring-house/40">{leg.date}</span>
        )}
        {leg.nessie_id && <span className="normal-case text-fog/70">{leg.nessie_id}</span>}
        <span className={`ml-auto ${LEG_STATUS[leg.status]}`}>{leg.status}</span>
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-3">
        <span className="min-w-0 text-lg">
          {name(leg.from)} <span className="text-fog">→</span> {dest}
        </span>
        <span className="shrink-0 font-mono text-lg font-bold tabular-nums">{money(leg.amount)}</span>
      </div>
    </li>
  );
}

function ProposalCard({ p, today, name }: { p: Proposal; today: string; name: (id: string) => string }) {
  return (
    <li className="animate-rise rounded-xl border border-line bg-panel-2/70 px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.2em] text-fog">{p.flow} · {p.id}</div>
          <div className="text-xl font-bold leading-snug">{p.title}</div>
        </div>
        <StatusBadge status={p.status} />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {p.required_approvers.map((rid) => {
          const v = VOTE[p.approvals[rid] ?? "pending"];
          return (
            <span key={rid} className={`flex items-center gap-2 rounded-full px-3 py-1 text-base ring-1 transition-colors duration-500 ${v.cls}`}>
              <span className="font-mono font-bold">{v.mark}</span>
              {name(rid)}
            </span>
          );
        })}
      </div>
      <ul className="mt-3">
        {p.legs.map((leg, i) => <LegRow key={i} leg={leg} today={today} name={name} />)}
      </ul>
    </li>
  );
}

export function Proposals({ proposals, today, name }: {
  proposals: Proposal[]; today: string; name: (id: string) => string;
}) {
  const open = proposals.filter((p) => p.status === "pending").length;
  return (
    <Panel title="Proposals" kicker={`${open} awaiting yes`}>
      {proposals.length === 0 ? (
        <Empty>No proposals yet. Money only moves after everyone says yes.</Empty>
      ) : (
        <ul className="space-y-4">
          {[...proposals].reverse().map((p) => <ProposalCard key={p.id} p={p} today={today} name={name} />)}
        </ul>
      )}
    </Panel>
  );
}
