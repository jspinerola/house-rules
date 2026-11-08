"use client";
import { useEffect, useRef } from "react";
import type { TraceEvent } from "../../../contracts/types";
import { clock, traceKey } from "../lib/brain";
import { AGENT_STYLE, Empty, Panel } from "./ui";

export function Trace({ trace }: { trace: TraceEvent[] }) {
  // Keys already on screen; null until the first render so the initial load doesn't animate.
  const seen = useRef<Set<string> | null>(null);
  const isNew = (k: string) => seen.current !== null && !seen.current.has(k);

  useEffect(() => {
    seen.current = new Set(trace.map(traceKey));
  }, [trace]);

  return (
    <Panel title="Agent trace" kicker="newest first">
      {trace.length === 0 ? (
        <Empty>Quiet. Trigger rent day to wake the agents.</Empty>
      ) : (
        <ol className="space-y-2">
          {trace.map((e) => {
            const k = traceKey(e);
            const s = AGENT_STYLE[e.agent];
            return (
              <li key={k} className={`flex gap-3 rounded-lg bg-panel-2/60 py-2 pr-3 ${isNew(k) ? "animate-slide-in" : ""}`}>
                <span className={`w-1.5 shrink-0 rounded-full ${s.bar}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`font-mono text-sm font-bold uppercase tracking-wider ${s.text}`}>
                      {s.label} <span className="text-paper">· {e.event}</span>
                    </span>
                    <span className="font-mono text-xs text-fog">{clock(e.ts)}</span>
                  </div>
                  <p className="break-words font-mono text-base text-paper/85">{e.detail}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
