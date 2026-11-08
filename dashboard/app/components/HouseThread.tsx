"use client";
import type { ThreadLine } from "../lib/brain";
import { clock } from "../lib/brain";
import { AGENT_STYLE, Empty, Panel } from "./ui";

/** Relay-mode fallback: the group replies, read from trace "replied to group" events. */
export function HouseThread({ lines }: { lines: ThreadLine[] }) {
  return (
    <Panel title="House thread" kicker="relay fallback">
      {lines.length === 0 ? (
        <Empty>Group replies appear here when the house agent speaks (relay mode).</Empty>
      ) : (
        <ol className="space-y-3">
          {lines.map((l) => (
            <li key={`${l.ts}|${l.text}`} className="animate-rise max-w-[92%] rounded-2xl rounded-bl-sm bg-house/12 px-4 py-2 ring-1 ring-house/30">
              <div className={`font-mono text-xs uppercase tracking-wider ${AGENT_STYLE[l.agent].text}`}>
                {AGENT_STYLE[l.agent].label} · {clock(l.ts)}
              </div>
              <p className="text-lg leading-snug">{l.text}</p>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
