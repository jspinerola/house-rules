"use client";
import { useEffect, useRef, useState } from "react";
import type { HouseState } from "../../../contracts/types";
import { Avatar, LevelTag, money, shortDate } from "./ui";

type Roommate = HouseState["roommates"][number];

function Balance({ value }: { value: number }) {
  const prev = useRef(value);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (prev.current !== value) {
      prev.current = value;
      setTick((n) => n + 1);
    }
  }, [value]);
  // Remounting on change restarts the highlight, so a balance that just moved is easy to spot.
  return (
    <span key={tick} className={`rounded-md px-1.5 py-0.5 text-lg font-semibold tabular-nums ${tick ? "animate-tick" : ""}`}>
      {money(value)}
    </span>
  );
}

export function Members({ roommates }: { roommates: Roommate[] }) {
  return (
    <ul className="divide-y divide-hairline">
      {roommates.map((r) => (
        <li key={r.id} className="flex items-center gap-4 py-3.5">
          <Avatar id={r.id} name={r.name} />
          <div className="min-w-0 flex-1">
            <div className="font-semibold">{r.name}</div>
            <LevelTag level={r.status} />
          </div>
          <div className="text-right">
            <Balance value={r.balance} />
            <div className="text-sm text-slate">
              {r.next_payday ? `Payday ${shortDate(r.next_payday)}` : "No payday set"}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}
