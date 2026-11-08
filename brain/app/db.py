"""SQLite Store (DB_MODE=sqlite). Schema SQL is kept Postgres-compatible for Tiger Data.

    python -m app.db --init     create an empty schema
"""
from __future__ import annotations

import json
import sqlite3
import sys
import threading

from contracts.models import (
    Account, ApprovalState, Bill, HouseRule, Leg, PayRule, Preferences, Proposal, Roommate, TraceEvent,
    Transaction,
)

from . import config, fixtures

SCHEMA = """
CREATE TABLE IF NOT EXISTS roommates (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, handle TEXT NOT NULL UNIQUE,
  monthly_income REAL NOT NULL, pay_amount REAL NOT NULL, pay_schedule TEXT NOT NULL,
  pay_day INTEGER, pay_anchor TEXT, next_payday TEXT NOT NULL, nessie_account_id TEXT
);
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY, roommate_id TEXT NOT NULL REFERENCES roommates(id), type TEXT NOT NULL,
  name TEXT NOT NULL, balance REAL NOT NULL, credit_limit REAL
);
CREATE TABLE IF NOT EXISTS transactions (
  id TEXT PRIMARY KEY, roommate_id TEXT NOT NULL REFERENCES roommates(id), date TEXT NOT NULL,
  description TEXT NOT NULL, category TEXT NOT NULL, amount REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS transactions_by_roommate ON transactions (roommate_id, date);
CREATE TABLE IF NOT EXISTS bills (
  id TEXT PRIMARY KEY, type TEXT NOT NULL UNIQUE, amount REAL NOT NULL, payee TEXT NOT NULL,
  payer TEXT NOT NULL, due TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS house_rules (
  id TEXT PRIMARY KEY, bill_type TEXT NOT NULL UNIQUE, split TEXT NOT NULL,
  source_text TEXT NOT NULL, confirmed_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
  id TEXT PRIMARY KEY, seq INTEGER NOT NULL, flow TEXT NOT NULL, title TEXT NOT NULL,
  status TEXT NOT NULL, rule TEXT
);
CREATE TABLE IF NOT EXISTS preferences (
  roommate_id TEXT PRIMARY KEY REFERENCES roommates(id), data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legs (
  proposal_id TEXT NOT NULL REFERENCES proposals(id), idx INTEGER NOT NULL, type TEXT NOT NULL,
  from_rid TEXT NOT NULL, to_rid TEXT, payee TEXT, amount REAL NOT NULL, date TEXT NOT NULL,
  status TEXT NOT NULL, nessie_id TEXT, PRIMARY KEY (proposal_id, idx)
);
CREATE TABLE IF NOT EXISTS approvals (
  proposal_id TEXT NOT NULL REFERENCES proposals(id), idx INTEGER NOT NULL,
  roommate_id TEXT NOT NULL, verdict TEXT NOT NULL, PRIMARY KEY (proposal_id, roommate_id)
);
CREATE TABLE IF NOT EXISTS trace (
  id INTEGER PRIMARY KEY, ts TEXT NOT NULL, agent TEXT NOT NULL, event TEXT NOT NULL, detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clock (id INTEGER PRIMARY KEY, today TEXT NOT NULL);
"""
TABLES = ["approvals", "legs", "proposals", "trace", "transactions", "accounts", "bills",
          "house_rules", "clock", "preferences", "roommates"]


class SqliteStore:
    def __init__(self, path: str | None = None) -> None:
        self.path = path or config.sqlite_path()
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        # executescript can clear connection pragmas; re-enable after schema apply
        self._db.execute("PRAGMA foreign_keys = ON")
        self._migrate()
        if self._db.execute("SELECT COUNT(*) FROM clock").fetchone()[0] == 0:
            self.reset()

    def _migrate(self) -> None:
        """Columns added after a house.db may already exist (CREATE IF NOT EXISTS skips them)."""
        cols = {r["name"] for r in self._db.execute("PRAGMA table_info(proposals)")}
        if "rule" not in cols:
            with self._db:
                self._db.execute("ALTER TABLE proposals ADD COLUMN rule TEXT")

    def _q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    # ----- seed / clock -----

    def reset(self) -> None:
        s = fixtures.scenario()
        with self._lock, self._db:
            for t in TABLES:
                self._db.execute(f"DELETE FROM {t}")
            for r in s.roommates:
                self._db.execute(
                    "INSERT INTO roommates VALUES (?,?,?,?,?,?,?,?,?,NULL)",
                    (r.id, r.name, r.handle, r.monthly_income, r.pay.amount, r.pay.schedule,
                     r.pay.day, r.pay.anchor, r.next_payday))
                for a in r.accounts:
                    self._db.execute("INSERT INTO accounts VALUES (?,?,?,?,?,?)",
                                     (a.id, r.id, a.type, a.name, a.balance, a.credit_limit))
            self._db.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?)",
                                 [(t.id, t.roommate_id, t.date, t.description, t.category, t.amount)
                                  for t in s.transactions])
            for b in s.bills:
                self._db.execute("INSERT INTO bills VALUES (?,?,?,?,?,?)",
                                 (b.id, b.type, b.amount, b.payee, b.payer, b.due))
            for h in s.house_rules:
                self._db.execute("INSERT INTO house_rules VALUES (?,?,?,?,?)",
                                 (h.id, h.bill_type, json.dumps(h.split), h.source_text,
                                  json.dumps(h.confirmed_by)))
            self._db.execute("INSERT INTO clock VALUES (1, ?)", (s.today,))

    def today(self) -> str:
        return self._q("SELECT today FROM clock WHERE id = 1")[0]["today"]

    def set_today(self, d: str) -> None:
        with self._lock, self._db:
            self._db.execute("UPDATE clock SET today = ? WHERE id = 1", (d,))

    # ----- roommates / history -----

    def _roommate(self, row: sqlite3.Row) -> Roommate:
        accounts = [Account(id=a["id"], type=a["type"], name=a["name"], balance=a["balance"],
                            credit_limit=a["credit_limit"])
                    for a in self._q("SELECT * FROM accounts WHERE roommate_id = ? ORDER BY id", (row["id"],))]
        return Roommate(id=row["id"], name=row["name"], handle=row["handle"],
                        monthly_income=row["monthly_income"],
                        pay=PayRule(amount=row["pay_amount"], schedule=row["pay_schedule"],
                                    day=row["pay_day"], anchor=row["pay_anchor"]),
                        next_payday=row["next_payday"], accounts=accounts)

    def get_roommate(self, rid: str) -> Roommate:
        rows = self._q("SELECT * FROM roommates WHERE id = ?", (rid,))
        if not rows:
            raise KeyError(f"unknown roommate {rid!r}")
        return self._roommate(rows[0])

    def by_handle(self, handle: str) -> Roommate | None:
        rows = self._q("SELECT * FROM roommates WHERE handle = ?", (handle,))
        return self._roommate(rows[0]) if rows else None

    def roommates(self) -> list[Roommate]:
        return [self._roommate(r) for r in self._q("SELECT * FROM roommates ORDER BY rowid")]

    def transactions(self, rid: str, since: str | None = None) -> list[Transaction]:
        rows = self._q("SELECT * FROM transactions WHERE roommate_id = ? AND date >= ? ORDER BY date, id",
                       (rid, since or ""))
        return [Transaction(**dict(r)) for r in rows]

    def add_transaction(self, txn: Transaction) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?)",
                             (txn.id, txn.roommate_id, txn.date, txn.description, txn.category, txn.amount))

    def bill(self, bill_type: str) -> Bill:
        rows = self._q("SELECT * FROM bills WHERE type = ?", (bill_type,))
        if not rows:
            raise KeyError(f"no bill of type {bill_type!r}")
        return Bill(**dict(rows[0]))

    def house_rule(self, bill_type: str) -> HouseRule | None:
        rows = self._q("SELECT * FROM house_rules WHERE bill_type = ?", (bill_type,))
        if not rows:
            return None
        return self._rule(rows[0])

    @staticmethod
    def _rule(r: sqlite3.Row) -> HouseRule:
        return HouseRule(id=r["id"], bill_type=r["bill_type"], split=json.loads(r["split"]),
                         source_text=r["source_text"], confirmed_by=json.loads(r["confirmed_by"]))

    def house_rules(self) -> list[HouseRule]:
        return [self._rule(r) for r in self._q("SELECT * FROM house_rules ORDER BY bill_type")]

    def save_house_rule(self, rule: HouseRule) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM house_rules WHERE bill_type = ?", (rule.bill_type,))
            self._db.execute("INSERT INTO house_rules VALUES (?,?,?,?,?)",
                             (rule.id, rule.bill_type, json.dumps(rule.split), rule.source_text,
                              json.dumps(rule.confirmed_by)))

    def delete_house_rule(self, bill_type: str) -> None:
        with self._lock, self._db:
            self._db.execute("DELETE FROM house_rules WHERE bill_type = ?", (bill_type,))

    def get_preferences(self, rid: str) -> Preferences:
        self.get_roommate(rid)  # KeyError on unknown rid
        rows = self._q("SELECT data FROM preferences WHERE roommate_id = ?", (rid,))
        return Preferences.model_validate_json(rows[0]["data"]) if rows else Preferences()

    def save_preferences(self, rid: str, prefs: Preferences) -> None:
        self.get_roommate(rid)
        with self._lock, self._db:
            self._db.execute("INSERT INTO preferences VALUES (?, ?) ON CONFLICT (roommate_id) "
                             "DO UPDATE SET data = excluded.data", (rid, prefs.model_dump_json()))

    # ----- proposals -----

    def save_proposal(self, p: Proposal) -> None:
        with self._lock, self._db:
            existing = self._db.execute(
                "SELECT seq FROM proposals WHERE id = ?", (p.id,)).fetchone()
            seq = existing["seq"] if existing else (
                self._db.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM proposals").fetchone()[0])
            self._db.execute(
                "INSERT INTO proposals (id, seq, flow, title, status, rule) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT (id) DO UPDATE SET flow = excluded.flow, title = excluded.title, "
                "status = excluded.status, rule = excluded.rule",
                (p.id, seq, p.flow, p.title, p.status, p.rule.model_dump_json() if p.rule else None))
            self._db.execute("DELETE FROM legs WHERE proposal_id = ?", (p.id,))
            self._db.executemany("INSERT INTO legs VALUES (?,?,?,?,?,?,?,?,?,?)", [
                (p.id, i, l.type, l.from_, l.to, l.payee, l.amount, l.date, l.status, l.nessie_id)
                for i, l in enumerate(p.legs)])
            self._db.execute("DELETE FROM approvals WHERE proposal_id = ?", (p.id,))
            self._db.executemany("INSERT INTO approvals VALUES (?,?,?,?)", [
                (p.id, i, rid, p.approvals.get(rid, "pending"))
                for i, rid in enumerate(p.required_approvers)])

    def _proposal(self, row: sqlite3.Row) -> Proposal:
        legs = [Leg(**{"from": l["from_rid"]}, type=l["type"], to=l["to_rid"], payee=l["payee"],
                    amount=l["amount"], date=l["date"], status=l["status"], nessie_id=l["nessie_id"])
                for l in self._q("SELECT * FROM legs WHERE proposal_id = ? ORDER BY idx", (row["id"],))]
        appr = self._q("SELECT roommate_id, verdict FROM approvals WHERE proposal_id = ? ORDER BY idx",
                       (row["id"],))
        approvals: dict[str, ApprovalState] = {a["roommate_id"]: a["verdict"] for a in appr}
        rule = HouseRule.model_validate_json(row["rule"]) if row["rule"] else None
        return Proposal(id=row["id"], flow=row["flow"], title=row["title"], legs=legs,
                        required_approvers=list(approvals), approvals=approvals, status=row["status"],
                        rule=rule)

    def get_proposal(self, pid: str) -> Proposal:
        rows = self._q("SELECT * FROM proposals WHERE id = ?", (pid,))
        if not rows:
            raise KeyError(f"unknown proposal {pid!r}")
        return self._proposal(rows[0])

    def proposals(self) -> list[Proposal]:
        return [self._proposal(r) for r in self._q("SELECT * FROM proposals ORDER BY seq")]

    def pending_for(self, rid: str) -> list[Proposal]:
        rows = self._q(
            "SELECT p.* FROM proposals p JOIN approvals a ON a.proposal_id = p.id "
            "WHERE p.status = 'pending' AND a.roommate_id = ? AND a.verdict = 'pending' ORDER BY p.seq",
            (rid,))
        return [self._proposal(r) for r in rows]

    # ----- trace -----

    def add_trace(self, e: TraceEvent) -> None:
        with self._lock, self._db:
            self._db.execute("INSERT INTO trace (ts, agent, event, detail) VALUES (?,?,?,?)",
                             (e.ts, e.agent, e.event, e.detail))

    def recent_trace(self, n: int = 50) -> list[TraceEvent]:
        rows = self._q("SELECT ts, agent, event, detail FROM trace ORDER BY id DESC LIMIT ?", (n,))
        return [TraceEvent(**dict(r)) for r in rows]


if __name__ == "__main__":
    if "--init" in sys.argv:
        store = SqliteStore()
        print(f"initialized {store.path}")
    else:
        print(__doc__)
