"use client";
import type { HouseRule } from "../../../contracts/types";
import { Empty, member } from "./ui";

/** Every roommate's share in percent: listed fractions, the rest split evenly (same as split_bill). */
export function rulePercents(rule: HouseRule, ids: string[]): { id: string; pct: number }[] {
  const listed = Object.values(rule.split).reduce((a, b) => a + b, 0);
  const rest = ids.filter((id) => !(id in rule.split));
  const each = rest.length ? (1 - listed) / rest.length : 0;
  return ids.map((id) => ({ id, pct: Math.round((rule.split[id] ?? each) * 1000) / 10 }));
}

const BILL: Record<string, string> = { rent: "Rent", electric: "Electric", purchase: "Shared purchases" };

export function RuleSplit({ rule, ids, name }: { rule: HouseRule; ids: string[]; name: (id: string) => string }) {
  if (Object.keys(rule.split).length === 0) return <div className="text-sm text-slate">Back to an even split</div>;
  const parts = rulePercents(rule, ids);
  return (
    <div>
      <div className="flex h-2 gap-0.5 overflow-hidden rounded-full">
        {parts.map((p) => (
          <span key={p.id} style={{ width: `${p.pct}%` }} className={`h-full ${member(p.id).fill}`} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {parts.map((p) => (
          <span key={p.id} className="text-slate">
            <span className={`font-semibold ${member(p.id).text}`}>{name(p.id)}</span> {p.pct}%
          </span>
        ))}
      </div>
    </div>
  );
}

export function HouseRules({ rules, ids, name }: { rules: HouseRule[]; ids: string[]; name: (id: string) => string }) {
  if (rules.length === 0) {
    return <Empty>No house rules yet, so every bill splits evenly. Agree on one in the group chat to add it.</Empty>;
  }
  return (
    <ul className="space-y-5">
      {rules.map((r) => (
        <li key={r.id} className="animate-enter">
          <div className="flex items-baseline justify-between gap-3">
            <span className="font-semibold">{BILL[r.bill_type] ?? r.bill_type}</span>
            {r.confirmed_by.length > 0 && (
              <span className="text-sm text-slate">Agreed by {r.confirmed_by.length === ids.length ? "everyone" : r.confirmed_by.map(name).join(", ")}</span>
            )}
          </div>
          <p className="mb-2.5 mt-0.5 text-sm text-slate">{r.source_text}</p>
          <RuleSplit rule={r} ids={ids} name={name} />
        </li>
      ))}
    </ul>
  );
}
