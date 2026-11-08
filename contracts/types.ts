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
  flow: "rent" | "front" | "purchase" | "utility" | "rule";
  title: string;
  legs: Leg[];
  required_approvers: string[];
  approvals: Record<string, "pending" | "yes" | "no">;
  status: "pending" | "approved" | "executed" | "rejected" | "failed";
  rule?: HouseRule | null; // flow "rule": the rule being voted on; split {} means remove it
};

export type HouseRule = {
  id: string;
  bill_type: string; // "rent" | "electric" | "purchase"
  split: Record<string, number>; // roommate_id -> fraction; the rest split evenly
  source_text: string; // the reason, e.g. "Xander has the master bedroom"
  confirmed_by: string[];
};

export type Preferences = {
  min_buffer?: number | null;
  savings_monthly?: number | null;
  savings_label?: string | null;
  front_cap?: number | null;
  notes: string[];
};

export type Profile = {
  income_pattern: "steady" | "steady_plus_side" | "irregular";
  regular_pay: number;
  side_income_monthly: number;
  recurring: { name: string; amount: number; next_date: string }[];
  spend_trend_pct: number;
  preferences: Preferences;
  indicators: Record<string, { value: number; status: "good" | "watch" | "risk"; inputs: Record<string, unknown> }>;
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
  rules: HouseRule[];
};

export type BankView = {
  bank_name: string;
  roommate_id: string;
  name: string;
  balance: number;
  transactions: { id: string; date: string; description: string; amount: number }[];
  scheduled: { date: string; description: string; amount: number }[];
  profile?: Profile | null;
};

export type Health = { ok: boolean; llm_mode: string; nessie_mode: string; modes: Record<string, string> };
// Body of every non-2xx brain response.
export type ErrorOut = { ok: false; error: string; detail: string | unknown[] };
