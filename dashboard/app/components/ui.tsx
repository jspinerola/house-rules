import type { ReactNode } from "react";
import type { Level, Proposal, TraceEvent } from "../../../contracts/types";

// Static class strings so Tailwind can see them.
export const AGENT_STYLE: Record<TraceEvent["agent"], { text: string; bar: string; label: string }> = {
  house: { text: "text-house", bar: "bg-house", label: "house" },
  "personal:alex": { text: "text-alex", bar: "bg-alex", label: "xander's agent" },
  "personal:sam": { text: "text-sam", bar: "bg-sam", label: "julian's agent" },
  "personal:jordan": { text: "text-jordan", bar: "bg-jordan", label: "kevin's agent" },
  treasurer: { text: "text-treasurer", bar: "bg-treasurer", label: "treasurer" },
  auditor: { text: "text-auditor", bar: "bg-auditor", label: "auditor" },
  watcher: { text: "text-watcher", bar: "bg-watcher", label: "watcher" },
};

const LEVEL_STYLE: Record<Level, string> = {
  ok: "bg-ok/15 text-ok ring-ok/50",
  tight: "bg-tight/15 text-tight ring-tight/50",
  no: "bg-no/15 text-no ring-no/50",
};

export function LevelPill({ level }: { level: Level }) {
  return (
    <span className={`rounded-full px-4 py-1 font-mono text-lg font-bold uppercase tracking-widest ring-2 ${LEVEL_STYLE[level]}`}>
      {level}
    </span>
  );
}

const STATUS_STYLE: Record<Proposal["status"], string> = {
  pending: "bg-tight/15 text-tight ring-tight/50",
  approved: "bg-house/15 text-house ring-house/50",
  executed: "bg-ok/15 text-ok ring-ok/50",
  rejected: "bg-no/15 text-no ring-no/50",
  failed: "bg-no/25 text-no ring-no",
};

export function StatusBadge({ status }: { status: Proposal["status"] }) {
  return (
    <span className={`shrink-0 rounded-md px-3 py-0.5 font-mono text-sm font-bold uppercase tracking-widest ring-1 ${STATUS_STYLE[status]}`}>
      {status}
    </span>
  );
}

export function Panel({ title, kicker, children, className = "" }: {
  title: string; kicker?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-2xl border border-line bg-panel/80 shadow-2xl shadow-black/40 backdrop-blur ${className}`}>
      <header className="flex items-baseline justify-between gap-4 border-b border-line px-6 py-4">
        <h2 className="text-2xl font-extrabold tracking-tight">{title}</h2>
        {kicker && <div className="font-mono text-sm text-fog">{kicker}</div>}
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-xl border border-dashed border-line px-4 py-6 text-center text-fog">{children}</p>;
}
