"use client";
import { useEffect, useState } from "react";
import type { Health } from "../../../contracts/types";
import type { AdvanceOut, OkOut } from "../lib/brain";
import { BRAIN_URL, post, usePoll } from "../lib/brain";

type Action = { label: string; run: () => Promise<string> };

const ACTIONS: Action[] = [
  { label: "Reset", run: async () => (await post<OkOut>("/demo/reset"), "reset to 2026-11-28") },
  {
    label: "Trigger rent_due",
    run: async () => (await post<OkOut>("/demo/trigger", { event: "rent_due" }), "rent_due triggered"),
  },
  {
    label: "Advance to 2026-12-16",
    run: async () => {
      const out = await post<AdvanceOut>("/demo/advance", { to: "2026-12-16" });
      return `clock -> 2026-12-16, ${out.executed.length} legs ran`;
    },
  },
];

/** Toggles open on the "d" key (ignored while typing in a field). */
function useToggleKey(key: string): boolean {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName))) return;
      if (e.key === key && !e.metaKey && !e.ctrlKey && !e.altKey) setOpen((o) => !o);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [key]);
  return open;
}

export function PresenterBar() {
  const open = useToggleKey("d");
  const health = usePoll<Health>("/health", 5000, open);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  if (!open) return null;

  const run = async (a: Action) => {
    setBusy(a.label);
    try {
      setMsg({ ok: true, text: await a.run() });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  };

  const h = health.data;
  return (
    <div className="animate-rise fixed inset-x-4 bottom-4 z-50 rounded-2xl border border-treasurer/50 bg-ink/95 px-5 py-4 shadow-2xl shadow-black/70 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-mono text-sm font-bold uppercase tracking-[0.2em] text-treasurer">presenter</span>
        {ACTIONS.map((a) => (
          <button
            key={a.label}
            disabled={busy !== null}
            onClick={() => run(a)}
            className="rounded-lg bg-panel-2 px-4 py-2 text-lg font-bold ring-1 ring-line transition hover:bg-line hover:ring-treasurer disabled:opacity-50"
          >
            {busy === a.label ? "…" : a.label}
          </button>
        ))}
        {msg && <span className={`font-mono text-sm ${msg.ok ? "text-ok" : "text-no"}`}>{msg.text}</span>}
        <span className="ml-auto font-mono text-xs text-fog">press d to hide · {BRAIN_URL}</span>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 font-mono text-sm">
        <span className={`h-3 w-3 rounded-full ${h?.ok && !health.error ? "bg-ok" : "bg-no"}`} />
        {health.error && <span className="text-no">{health.error}</span>}
        {h && (
          <>
            <span className="rounded bg-house/15 px-2 py-0.5 text-house">llm={h.llm_mode}</span>
            <span className="rounded bg-house/15 px-2 py-0.5 text-house">nessie={h.nessie_mode}</span>
            {Object.entries(h.modes).map(([k, v]) => (
              <span key={k} className={`rounded px-2 py-0.5 ${v === "stub" ? "bg-panel-2 text-fog" : "bg-ok/15 text-ok"}`}>
                {k}={v}
              </span>
            ))}
          </>
        )}
        {!h && !health.error && <span className="text-fog">loading /health …</span>}
      </div>
    </div>
  );
}
