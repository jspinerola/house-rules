"use client";
import { useEffect, useRef, useState } from "react";
import type { HouseState } from "../../../contracts/types";
import { money } from "../lib/brain";
import { Empty, LevelPill, Panel } from "./ui";

type Roommate = HouseState["roommates"][number];

function Balance({ value }: { value: number }) {
  const prev = useRef(value);
  const [flash, setFlash] = useState(0);
  useEffect(() => {
    if (prev.current !== value) {
      prev.current = value;
      setFlash((n) => n + 1);
    }
  }, [value]);
  // Remounting the span on each change restarts the flash animation.
  return (
    <span key={flash} className={`text-[2.2rem] font-extrabold leading-none tabular-nums ${flash ? "animate-flash" : ""}`}>
      {money(value)}
    </span>
  );
}

function RoommateCard({ r, index }: { r: Roommate; index: number }) {
  return (
    <li
      className="animate-rise rounded-xl border border-line bg-panel-2/70 px-5 py-4"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-2xl font-bold">{r.name}</span>
        <LevelPill level={r.status} />
      </div>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-2">
        <Balance value={r.balance} />
        <span className="font-mono text-base text-fog">
          payday <span className="text-paper">{r.next_payday || "none"}</span>
        </span>
      </div>
    </li>
  );
}

export function Roommates({ state, name }: { state: HouseState; name: (id: string) => string }) {
  return (
    <Panel title="Roommates" kicker="ok / tight / no for rent">
      <ul className="space-y-4">
        {state.roommates.map((r, i) => <RoommateCard key={r.id} r={r} index={i} />)}
      </ul>
      <h3 className="mb-3 mt-8 text-xl font-bold text-fog">Who owes whom</h3>
      {state.owes.length === 0 ? (
        <Empty>All square.</Empty>
      ) : (
        <ul className="space-y-2">
          {state.owes.map((o, i) => (
            <li key={`${o.from}-${o.to}-${o.due}-${i}`} className="animate-rise flex flex-wrap items-center justify-between gap-2 rounded-lg bg-panel-2/60 px-4 py-3">
              <span className="text-lg">
                <b>{name(o.from)}</b> <span className="text-fog">owes</span> <b>{name(o.to)}</b>
              </span>
              <span className="font-mono text-lg">
                <span className="font-bold text-tight">{money(o.amount)}</span>
                <span className="text-fog"> by {o.due}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
