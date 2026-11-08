"use client";
// Brain HTTP client for the house view. Errors surface as thrown messages, never silent defaults.
import { useEffect, useState } from "react";
import type { ErrorOut, Leg, TraceEvent } from "../../../contracts/types";

export const BRAIN_URL = (process.env.NEXT_PUBLIC_BRAIN_URL ?? "http://localhost:8000").replace(/\/$/, "");

export type OkOut = { ok: boolean };
export type AdvanceOut = { ok: boolean; executed: Leg[] };

async function parse<T>(res: Response, label: string): Promise<T> {
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body as Partial<ErrorOut> | null;
    const detail = err?.detail === undefined ? "" : `: ${typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail)}`;
    throw new Error(`${label} -> ${res.status} ${err?.error ?? ""}${detail}`.trim());
  }
  if (body === null) throw new Error(`${label} -> ${res.status} with a non-JSON body`);
  return body as T;
}

export async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${BRAIN_URL}${path}`, { cache: "no-store" });
  return parse<T>(res, `GET ${path}`);
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BRAIN_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return parse<T>(res, `POST ${path}`);
}

/** Poll `path` every `ms` while enabled. Keeps the last good data when a poll fails. */
export function usePoll<T>(path: string, ms: number, enabled = true): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    const load = async () => {
      try {
        const next = await getJSON<T>(path);
        if (alive) {
          setData(next);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      }
    };
    load();
    const id = setInterval(load, ms);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [path, ms, enabled]);

  return { data, error };
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
export const money = (n: number) => usd.format(n);

export type ThreadLine = { ts: string; agent: TraceEvent["agent"]; text: string };

const GROUP_PREFIX = "to group: ";

/** Group replies logged by the agents' voice step (relay mode fallback), oldest first. */
export function threadFromTrace(trace: TraceEvent[]): ThreadLine[] {
  return trace
    .filter((e) => e.event === "replied" && e.detail.startsWith(GROUP_PREFIX))
    .map((e) => ({ ts: e.ts, agent: e.agent, text: e.detail.slice(GROUP_PREFIX.length) }))
    .reverse();
}

export const traceKey = (e: TraceEvent) => `${e.ts}|${e.agent}|${e.event}|${e.detail}`;

export function clock(ts: string): string {
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleTimeString("en-US", { hour12: false });
}
