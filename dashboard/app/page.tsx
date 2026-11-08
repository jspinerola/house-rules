"use client";
// House view (P0, unstyled): polls GET /state every 2 s. Styling lands in D6.
import { useEffect, useState } from "react";
import type { HouseState } from "../../contracts/types";

const BRAIN_URL = process.env.NEXT_PUBLIC_BRAIN_URL ?? "http://localhost:8000";

async function post(path: string, body?: unknown) {
  await fetch(`${BRAIN_URL}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export default function Page() {
  const [state, setState] = useState<HouseState | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const res = await fetch(`${BRAIN_URL}/state`, { cache: "no-store" });
        if (!res.ok) throw new Error(`GET /state -> ${res.status}`);
        const data = (await res.json()) as HouseState;
        if (alive) setState(data), setError(null);
      } catch (e) {
        if (alive) setError((e as Error).message);
      }
    };
    load();
    const id = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  if (!state) return <p>{error ?? "loading /state ..."}</p>;
  return (
    <main>
      <h1>House Rules - {state.today}</h1>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <section>
          <h2>Roommates</h2>
          <ul>
            {state.roommates.map((r) => (
              <li key={r.id}>
                {r.name}: ${r.balance.toFixed(2)} [{r.status}] next payday {r.next_payday}
              </li>
            ))}
          </ul>
          <h3>Who owes whom</h3>
          <ul>
            {state.owes.map((o, i) => (
              <li key={i}>
                {o.from} owes {o.to} ${o.amount.toFixed(2)} by {o.due}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2>Proposals</h2>
          {state.proposals.map((p) => (
            <div key={p.id}>
              <strong>{p.title}</strong> ({p.status})
              <div>
                {p.required_approvers.map((r) => (
                  <span key={r}>
                    {r} {p.approvals[r] === "yes" ? "[x]" : p.approvals[r] === "no" ? "[no]" : "[ ]"}{" "}
                  </span>
                ))}
              </div>
              <ul>
                {p.legs.map((l, i) => (
                  <li key={i}>
                    {l.date} {l.type} {l.from} -&gt; {l.to ?? l.payee} ${l.amount.toFixed(2)} [{l.status}]
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
        <section>
          <h2>Agent trace</h2>
          <ol>
            {state.trace.map((e, i) => (
              <li key={i}>
                [{e.agent}] {e.event}: {e.detail}
              </li>
            ))}
          </ol>
        </section>
      </div>
      <details>
        <summary>presenter</summary>
        <button onClick={() => post("/demo/reset")}>reset</button>{" "}
        <button onClick={() => post("/demo/trigger", { event: "rent_due" })}>trigger rent</button>{" "}
        <button onClick={() => post("/demo/advance", { to: "2026-12-16" })}>advance to 12-16</button>
      </details>
      <details>
        <summary>raw /state</summary>
        <pre>{JSON.stringify(state, null, 2)}</pre>
      </details>
      <footer>Synthetic data only. Not financial advice.</footer>
    </main>
  );
}
