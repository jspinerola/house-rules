"use client";
// House view: polls GET /state every 2 s. Press "d" for presenter controls.
import { useCallback, useMemo } from "react";
import type { HouseState } from "../../contracts/types";
import { Activity } from "./components/Activity";
import { Approvals } from "./components/Approvals";
import { Circle } from "./components/Circle";
import { HouseRules } from "./components/HouseRules";
import { Members } from "./components/Members";
import { PresenterBar } from "./components/PresenterBar";
import { Section, longDate } from "./components/ui";
import { BRAIN_URL, usePoll } from "./lib/brain";

const HOUSE_NAME = process.env.NEXT_PUBLIC_HOUSE_NAME ?? "Maple Court";

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className="h-9 w-9">
      <circle cx="16" cy="16" r="13" fill="none" stroke="#14171c" strokeWidth="2.2" />
      <circle cx="16" cy="3" r="3.2" fill="#3366ff" />
      <circle cx="27.3" cy="22.5" r="3.2" fill="#f2694b" />
      <circle cx="4.7" cy="22.5" r="3.2" fill="#14a3a3" />
    </svg>
  );
}

const list = (names: string[]) =>
  names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;

export default function Page() {
  const { data: state, error } = usePoll<HouseState>("/state", 2000);
  const names = useMemo(() => new Map(state?.roommates.map((r) => [r.id, r.name]) ?? []), [state]);
  const name = useCallback((id: string) => names.get(id) ?? id, [names]);

  const pending = useMemo(() => {
    const out: Record<string, number> = {};
    for (const p of state?.proposals ?? []) {
      if (p.status !== "pending") continue;
      for (const [rid, v] of Object.entries(p.approvals)) if (v === "pending") out[rid] = (out[rid] ?? 0) + 1;
    }
    return out;
  }, [state]);
  const open = state?.proposals.filter((p) => p.status === "pending").length ?? 0;

  return (
    <main className="mx-auto flex min-h-screen max-w-[1440px] flex-col px-5 pb-16 pt-6 sm:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4 pb-6">
        <div className="flex items-center gap-3.5">
          <Mark />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{HOUSE_NAME}</h1>
            <p className="text-sm text-slate">{state ? list(state.roommates.map((r) => r.name)) : "House Rules"}</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {state && <span className="text-sm text-slate">{longDate(state.today)}</span>}
          <span className={`flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${error ? "bg-no/10 text-no" : "bg-ok/10 text-ok"}`}>
            <span className={`h-2 w-2 rounded-full ${error ? "bg-no" : "animate-pulse bg-ok"}`} />
            {error ? "Reconnecting" : "Live"}
          </span>
        </div>
      </header>

      {!state ? (
        <div className="m-auto max-w-md text-center">
          <p className="text-lg font-semibold">{error ? "Can't reach the house server" : "Connecting to your house"}</p>
          <p className="mt-1 text-sm text-slate">
            {error ? `Start the brain at ${BRAIN_URL}, then this page connects on its own.` : "One moment."}
          </p>
        </div>
      ) : (
        <div className="grid flex-1 grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          <div className="space-y-6">
            <div className="rounded-[2rem] bg-[radial-gradient(circle_at_50%_52%,#ffffff_0%,#ffffff_38%,#f4f6f8_100%)] px-2 pt-2">
              <Circle state={state} houseName={HOUSE_NAME} pending={pending} />
            </div>
            <Members roommates={state.roommates} />
          </div>

          <div className="space-y-8">
            <Section title="Needs a yes" aside={open ? `${open} open` : undefined}>
              <Approvals proposals={state.proposals} today={state.today} name={name} />
            </Section>
            <Section title="House rules">
              <HouseRules rules={state.rules ?? []} ids={state.roommates.map((r) => r.id)} name={name} />
            </Section>
            <Section title="Activity">
              <Activity trace={state.trace} proposals={state.proposals} name={name} />
            </Section>
          </div>
        </div>
      )}
      <PresenterBar />
    </main>
  );
}
