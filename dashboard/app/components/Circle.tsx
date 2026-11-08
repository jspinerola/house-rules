"use client";
import type { HouseState } from "../../../contracts/types";
import { LEVEL, initial, member, money, shortDate } from "./ui";

type Roommate = HouseState["roommates"][number];

const W = 640;
const H = 545;
const C = { x: W / 2, y: 282 };
const R = 172; // orbit radius
const AV = 40; // avatar radius
const RING = 47; // status ring radius

type Pt = { x: number; y: number };

function seat(i: number, n: number): Pt {
  const a = ((-90 + (360 / n) * i) * Math.PI) / 180;
  return { x: C.x + R * Math.cos(a), y: C.y + R * Math.sin(a) };
}

/** Money owed between two roommates, summed, with the earliest due date. */
function threads(owes: HouseState["owes"]) {
  const by = new Map<string, { from: string; to: string; amount: number; due: string }>();
  for (const o of owes) {
    const k = `${o.from}>${o.to}`;
    const t = by.get(k);
    if (t) {
      t.amount = Math.round((t.amount + o.amount) * 100) / 100;
      if (o.due < t.due) t.due = o.due;
    } else by.set(k, { ...o });
  }
  return [...by.values()];
}

/** A curve from a's edge to b's edge that bows away from the house. */
function curve(a: Pt, b: Pt) {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  const ctl = { x: mid.x + (mid.x - C.x) * 0.55, y: mid.y + (mid.y - C.y) * 0.55 };
  const edge = (p: Pt, toward: Pt, r: number) => {
    const dx = toward.x - p.x, dy = toward.y - p.y, d = Math.hypot(dx, dy) || 1;
    return { x: p.x + (dx / d) * r, y: p.y + (dy / d) * r };
  };
  const p0 = edge(a, ctl, RING + 6);
  const p2 = edge(b, ctl, RING + 12);
  const label = { x: 0.25 * p0.x + 0.5 * ctl.x + 0.25 * p2.x, y: 0.25 * p0.y + 0.5 * ctl.y + 0.25 * p2.y };
  return { d: `M ${p0.x} ${p0.y} Q ${ctl.x} ${ctl.y} ${p2.x} ${p2.y}`, label };
}

export function Circle({ state, houseName, pending }: {
  state: HouseState; houseName: string; pending: Record<string, number>;
}) {
  const people = state.roommates;
  const seats = new Map(people.map((r, i) => [r.id, seat(i, people.length)]));
  const name = (id: string) => people.find((r) => r.id === id)?.name ?? id;
  const lines = threads(state.owes).filter((t) => seats.has(t.from) && seats.has(t.to));
  const summary =
    `${houseName}: ${people.map((r) => `${r.name} ${LEVEL[r.status].label.toLowerCase()}`).join(", ")}. ` +
    (lines.length
      ? lines.map((t) => `${name(t.from)} owes ${name(t.to)} ${money(t.amount)} by ${shortDate(t.due)}`).join(". ")
      : "Nobody owes anyone.");
  const orbit = 2 * Math.PI * R;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} className="h-auto w-full">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 1 L 8 5 L 0 9 z" fill="#14171c" />
        </marker>
      </defs>

      {/* Orbit: the one load-in moment */}
      <circle cx={C.x} cy={C.y} r={R + 70} fill="none" stroke="#f4f6f8" strokeWidth={1} />
      <circle
        cx={C.x} cy={C.y} r={R} fill="none" stroke="#e4e7ec" strokeWidth={1.5}
        strokeDasharray={orbit} className="animate-draw" style={{ ["--len" as string]: orbit }}
        transform={`rotate(-90 ${C.x} ${C.y})`}
      />

      {/* The house */}
      <g>
        <rect x={C.x - 46} y={C.y - 46} width={92} height={92} rx={28} fill="#f4f6f8" />
        <path
          d={`M ${C.x - 20} ${C.y - 2} L ${C.x} ${C.y - 20} L ${C.x + 20} ${C.y - 2} V ${C.y + 20} H ${C.x + 6} V ${C.y + 8} H ${C.x - 6} V ${C.y + 20} H ${C.x - 20} Z`}
          fill="none" stroke="#14171c" strokeWidth={2.4} strokeLinejoin="round"
        />
        <text x={C.x} y={C.y + 74} textAnchor="middle" className="fill-ink text-[17px] font-semibold">{houseName}</text>
      </g>

      {/* Money threads */}
      {lines.map((t) => {
        const { d, label } = curve(seats.get(t.from)!, seats.get(t.to)!);
        const text = `${money(t.amount)} by ${shortDate(t.due)}`;
        const w = text.length * 7.6 + 22;
        return (
          <g key={`${t.from}>${t.to}`}>
            <path d={d} fill="none" stroke="#14171c" strokeWidth={1.6} strokeDasharray="5 6" markerEnd="url(#arrow)" />
            <rect x={label.x - w / 2} y={label.y - 14} width={w} height={28} rx={14} fill="#ffffff" stroke="#e4e7ec" />
            <text x={label.x} y={label.y + 5} textAnchor="middle" className="fill-ink text-[13px] font-semibold">{text}</text>
          </g>
        );
      })}

      {/* Roommates */}
      {people.map((r: Roommate, i) => {
        const p = seats.get(r.id)!;
        const m = member(r.id);
        const waiting = pending[r.id] ?? 0;
        const below = p.y >= C.y - 10;
        const ly = below ? p.y + RING + 26 : p.y - RING - 34;
        return (
          <g key={r.id}>
            <g className="animate-pop" style={{ animationDelay: `${350 + i * 140}ms`, transformBox: "fill-box", transformOrigin: "center" }}>
              <circle cx={p.x} cy={p.y} r={RING} fill="#ffffff" stroke={LEVEL[r.status].hex} strokeWidth={5} />
              <circle cx={p.x} cy={p.y} r={AV} fill={m.hex} />
              <text x={p.x} y={p.y + 9} textAnchor="middle" className="fill-white text-[26px] font-semibold">{initial(r.name)}</text>
              {waiting > 0 && (
                <g>
                  <circle cx={p.x + 34} cy={p.y - 34} r={13} fill="#14171c" stroke="#ffffff" strokeWidth={3} />
                  <text x={p.x + 34} y={p.y - 29.5} textAnchor="middle" className="fill-white text-[13px] font-bold">{waiting}</text>
                </g>
              )}
            </g>
            <text x={p.x} y={ly} textAnchor="middle" className="fill-ink text-[17px] font-semibold">{r.name}</text>
            <text x={p.x} y={ly + 19} textAnchor="middle" className="text-[13px] font-medium" fill={LEVEL[r.status].hex}>
              {LEVEL[r.status].label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
