"use client";
import type { HouseRule } from "../../../contracts/types";
import { Empty, Panel } from "./ui";

/** Every roommate's share in percent: listed fractions, the rest split evenly (same as split_bill). */
export function rulePercents(rule: HouseRule, ids: string[]): { id: string; pct: number; set: boolean }[] {
  const listed = Object.values(rule.split).reduce((a, b) => a + b, 0);
  const rest = ids.filter((id) => !(id in rule.split));
  const each = rest.length ? (1 - listed) / rest.length : 0;
  return ids.map((id) => ({ id, pct: Math.round((rule.split[id] ?? each) * 1000) / 10, set: id in rule.split }));
}

export function RuleSplit({ rule, ids, name }: { rule: HouseRule; ids: string[]; name: (id: string) => string }) {
  if (Object.keys(rule.split).length === 0) {
    return <div className="font-mono text-sm text-fog">back to an even split</div>;
  }
  const parts = rulePercents(rule, ids);
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-panel-2 ring-1 ring-line">
        {parts.map((p, i) => (
          <span key={p.id} style={{ width: `${p.pct}%` }}
                className={`h-full ${["bg-alex", "bg-sam", "bg-jordan"][i % 3]} ${i ? "border-l border-panel" : ""}`} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-sm">
        {parts.map((p) => (
          <span key={p.id} className={p.set ? "" : "text-fog"}>
            {name(p.id)} {p.pct}%
          </span>
        ))}
      </div>
    </div>
  );
}

export function HouseRules({ rules, ids, name }: { rules: HouseRule[]; ids: string[]; name: (id: string) => string }) {
  return (
    <Panel title="House rules" kicker="set in chat, everyone agreed">
      {rules.length === 0 ? (
        <Empty>No house rules yet. Every bill splits evenly.</Empty>
      ) : (
        <ul className="space-y-4">
          {rules.map((r) => (
            <li key={r.id} className="animate-rise rounded-xl border border-line bg-panel-2/70 px-5 py-4">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-xl font-bold capitalize">{r.bill_type}</span>
                <span className="font-mono text-xs uppercase tracking-[0.2em] text-fog">
                  {r.confirmed_by.length ? `agreed by ${r.confirmed_by.map(name).join(", ")}` : "seeded"}
                </span>
              </div>
              <p className="mb-3 mt-1 text-base text-fog">“{r.source_text}”</p>
              <RuleSplit rule={r} ids={ids} name={name} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
