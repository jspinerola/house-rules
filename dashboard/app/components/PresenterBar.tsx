"use client";
import { useEffect, useState } from "react";
import type { Health } from "../../../contracts/types";
import type { AdvanceOut, OkOut } from "../lib/brain";
import { post, usePoll } from "../lib/brain";

type Action = { label: string; run: () => Promise<string> };

const ACTIONS: Action[] = [
  { label: "Start over", run: async () => (await post<OkOut>("/demo/reset"), "Back to the start") },
  { label: "Rent is due", run: async () => (await post<OkOut>("/demo/trigger", { event: "rent_due" }), "Rent posted to the group") },
  { label: "Electric bill", run: async () => (await post<OkOut>("/demo/trigger", { event: "electric_bill" }), "Electric bill posted") },
  {
    label: "Jump to Dec 16",
    run: async () => {
      const out = await post<AdvanceOut>("/demo/advance", { to: "2026-12-16" });
      return `Moved to Dec 16, ${out.executed.length} scheduled ${out.executed.length === 1 ? "payment" : "payments"} ran`;
    },
  },
];

/** Opens on the "d" key (ignored while typing in a field). */
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
  const offline = h ? Object.entries(h.modes).filter(([, v]) => v === "stub").map(([k]) => k) : [];
  return (
    <div role="toolbar" aria-label="Presenter controls"
      className="animate-enter fixed inset-x-4 bottom-4 z-50 mx-auto flex max-w-4xl flex-wrap items-center gap-2 rounded-2xl border border-hairline bg-white/95 px-4 py-3 shadow-[0_12px_40px_rgb(20_23_28/0.12)] backdrop-blur">
      {ACTIONS.map((a) => (
        <button key={a.label} type="button" disabled={busy !== null} onClick={() => run(a)}
          className="rounded-full border border-hairline px-4 py-1.5 text-sm font-medium transition-colors hover:border-ink disabled:opacity-50">
          {busy === a.label ? "Working…" : a.label}
        </button>
      ))}
      {msg && <span className={`text-sm ${msg.ok ? "text-slate" : "text-no"}`}>{msg.text}</span>}
      <span className="ml-auto flex items-center gap-2 text-xs text-slate">
        <span className={`h-2 w-2 rounded-full ${h?.ok && !health.error ? "bg-ok" : "bg-no"}`} />
        {health.error ? "Server unreachable" : !h ? "Checking services" : offline.length ? `Offline: ${offline.join(", ")}` : "All services live"}
      </span>
    </div>
  );
}
