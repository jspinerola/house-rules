"use client";
// House view for the projector: polls GET /state every 2 s. Press "d" for presenter controls.
import { useCallback, useMemo } from "react";
import type { HouseState } from "../../contracts/types";
import { HouseThread } from "./components/HouseThread";
import { PresenterBar } from "./components/PresenterBar";
import { Proposals } from "./components/Proposals";
import { Roommates } from "./components/Roommates";
import { Trace } from "./components/Trace";
import { BRAIN_URL, threadFromTrace, usePoll } from "./lib/brain";

export default function Page() {
  const { data: state, error } = usePoll<HouseState>("/state", 2000);

  const names = useMemo(() => new Map(state?.roommates.map((r) => [r.id, r.name]) ?? []), [state]);
  const name = useCallback((id: string) => names.get(id) ?? id, [names]);
  const thread = useMemo(() => threadFromTrace(state?.trace ?? []), [state]);

  return (
    <main className="mx-auto flex min-h-screen max-w-[1920px] flex-col gap-5 px-4 py-5 sm:px-8 lg:h-screen">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="font-mono text-sm uppercase tracking-[0.35em] text-house">house view</div>
          <h1 className="text-5xl font-extrabold tracking-tight sm:text-6xl">
            House Rules<span className="text-house">.</span>
          </h1>
        </div>
        <div className="flex items-end gap-6">
          <div className="text-right">
            <div className="font-mono text-sm uppercase tracking-[0.3em] text-fog">demo clock</div>
            <div className="font-mono text-4xl font-bold tabular-nums sm:text-5xl">{state?.today ?? "----------"}</div>
          </div>
          <span
            title={error ?? "live"}
            className={`mb-2 flex items-center gap-2 rounded-full px-3 py-1 font-mono text-sm ring-1 ${
              error ? "bg-no/15 text-no ring-no/50" : "bg-ok/10 text-ok ring-ok/40"
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full ${error ? "bg-no" : "animate-pulse bg-ok"}`} />
            {error ? "stale" : "live"}
          </span>
        </div>
      </header>

      {error && (
        <p className="rounded-xl border border-no/50 bg-no/10 px-4 py-2 font-mono text-base text-no">
          {error} ({BRAIN_URL})
        </p>
      )}

      {!state ? (
        <p className="m-auto font-mono text-2xl text-fog">{error ? "brain unreachable" : "loading /state …"}</p>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-5 lg:grid-cols-3">
          <Roommates state={state} name={name} />
          <Proposals proposals={state.proposals} today={state.today} name={name} />
          <div className="grid min-h-0 gap-5 lg:grid-rows-[3fr_2fr]">
            <Trace trace={state.trace} />
            <HouseThread lines={thread} />
          </div>
        </div>
      )}

      <footer className="text-center font-mono text-xs text-fog">Synthetic data only. Not financial advice.</footer>
      <PresenterBar />
    </main>
  );
}
