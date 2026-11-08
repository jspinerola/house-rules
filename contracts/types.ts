// TypeScript mirror of contracts/models.py (frozen). Used by gateway, dashboard, bank-app.

export type Level = "ok" | "tight" | "no";

export type ChatIn = {
  chat_type: "group" | "dm";
  sender_handle: string;
  text: string;
  message_id: string;
  ts: string;
};

export type Target = { type: "group" } | { type: "dm"; roommate_id: string };
export type Reply = { target: Target; text: string };
export type ChatOut = { replies: Reply[] };
export type SendIn = Reply;

export type Leg = {
  type: "transfer" | "scheduled_transfer" | "bill_payment" | "purchase";
  from: string;
  to?: string | null;
  payee?: string | null;
  amount: number;
  date: string;
  status: "pending" | "done" | "failed";
  nessie_id?: string | null;
};

export type Proposal = {
  id: string;
  flow: "rent" | "front" | "purchase" | "utility";
  title: string;
  legs: Leg[];
  required_approvers: string[];
  approvals: Record<string, "pending" | "yes" | "no">;
  status: "pending" | "approved" | "executed" | "rejected" | "failed";
};

export type TraceEvent = {
  ts: string;
  agent: "house" | "personal:alex" | "personal:sam" | "personal:jordan" | "treasurer" | "auditor" | "watcher";
  event: string;
  detail: string;
};

export type HouseState = {
  today: string;
  roommates: { id: string; name: string; balance: number; status: Level; next_payday: string }[];
  owes: { from: string; to: string; amount: number; due: string }[];
  proposals: Proposal[];
  trace: TraceEvent[];
};

export type BankView = {
  bank_name: string;
  roommate_id: string;
  name: string;
  balance: number;
  transactions: { id: string; date: string; description: string; amount: number }[];
  scheduled: { date: string; description: string; amount: number }[];
};

export type Health = { ok: boolean; llm_mode: string; nessie_mode: string; modes: Record<string, string> };
// Body of every non-2xx brain response.
export type ErrorOut = { ok: false; error: string; detail: string | unknown[] };
