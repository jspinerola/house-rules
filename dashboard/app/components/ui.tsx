import type { ReactNode } from "react";
import type { Level, Proposal } from "../../../contracts/types";

// Static class strings so Tailwind can see them. Keyed by roommate id.
const MEMBER: Record<string, { fill: string; text: string; soft: string; hex: string }> = {
  alex: { fill: "bg-alex", text: "text-alex", soft: "bg-alex/10", hex: "#3366ff" },
  sam: { fill: "bg-sam", text: "text-sam", soft: "bg-sam/10", hex: "#f2694b" },
  jordan: { fill: "bg-jordan", text: "text-jordan", soft: "bg-jordan/10", hex: "#14a3a3" },
};
const FALLBACK = { fill: "bg-slate", text: "text-slate", soft: "bg-mist", hex: "#667085" };
export const member = (id: string) => MEMBER[id] ?? FALLBACK;

export const LEVEL: Record<Level, { label: string; dot: string; text: string; hex: string }> = {
  ok: { label: "On track", dot: "bg-ok", text: "text-ok", hex: "#16a34a" },
  tight: { label: "Tight", dot: "bg-tight", text: "text-tight", hex: "#e5a000" },
  no: { label: "Short until payday", dot: "bg-no", text: "text-no", hex: "#e5484d" },
};

export const initial = (name: string) => name.trim().charAt(0).toUpperCase() || "?";

export function Avatar({ id, name, size = "md" }: { id: string; name: string; size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-7 w-7 text-xs" : "h-10 w-10 text-base";
  return (
    <span aria-hidden className={`inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white ${box} ${member(id).fill}`}>
      {initial(name)}
    </span>
  );
}

export function LevelTag({ level }: { level: Level }) {
  const s = LEVEL[level];
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${s.text}`}>
      <span className={`h-2 w-2 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

const STATUS: Record<Proposal["status"], { label: string; cls: string }> = {
  pending: { label: "Waiting", cls: "bg-tight/12 text-[#9a6b00]" },
  approved: { label: "Approved", cls: "bg-alex/10 text-alex" },
  executed: { label: "Done", cls: "bg-ok/10 text-ok" },
  rejected: { label: "Declined", cls: "bg-mist text-slate" },
  failed: { label: "Failed", cls: "bg-no/10 text-no" },
};

export function Status({ status }: { status: Proposal["status"] }) {
  const s = STATUS[status];
  return <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${s.cls}`}>{s.label}</span>;
}

export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="border-t border-hairline pt-5 first:border-t-0 first:pt-0">
      <header className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {aside && <div className="text-sm text-slate">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm leading-relaxed text-slate">{children}</p>;
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
export const money = (n: number) => usd.format(n).replace(/\.00$/, "");

/** "2026-12-16" -> "Dec 16" without timezone drift. */
export function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function longDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    weekday: "long", month: "long", day: "numeric", timeZone: "UTC",
  });
}
