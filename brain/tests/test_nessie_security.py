"""Rigid isolation/determinism tests for Nessie stub + LiveNessie (MockTransport)."""
from __future__ import annotations

import json
import re

import httpx
import pytest

from app import fixtures, registry
from app.nessie import LiveNessie
from contracts.interfaces import NessieError
from contracts.models import Scenario


# ----- stub -----

@pytest.fixture
def stub(use):
    use(nessie="stub", store="stub")
    n = registry.get("nessie")
    n.seed(fixtures.scenario())
    return n


def test_stub_seed_balances(stub):
    assert (stub.balance("alex"), stub.balance("sam"), stub.balance("jordan")) == (4200, 2600, 310)


def test_stub_transfer_moves_both_sides(stub):
    tid = stub.transfer("sam", "alex", 800, "rent share")
    assert tid
    assert stub.balance("sam") == 1800 and stub.balance("alex") == 5000


def test_stub_unknown_rid_raises(stub):
    with pytest.raises(KeyError):
        stub.balance("nobody")
    with pytest.raises(KeyError):
        stub.transfer("alex", "nobody", 1, "x")


def test_stub_negative_amount_raises(stub):
    with pytest.raises(ValueError):
        stub.transfer("sam", "alex", -1, "bad")
    with pytest.raises(ValueError):
        stub.purchase("alex", "X", float("nan"), "bad")


def test_stub_transactions_newest_first_outflows_negative(stub):
    stub.purchase("alex", "Poison Co", 10, "snack")
    txns = stub.transactions("alex")
    dates = [t.date for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert txns[0].amount == -10


def test_stub_isolation_alex_purchase_does_not_change_jordan(stub):
    before = stub.balance("jordan")
    stub.purchase("alex", "Poison Co", 100, "iso")
    assert stub.balance("jordan") == before


# ----- live MockTransport -----

API_KEY = "test-key-not-real"


def _scenario() -> Scenario:
    return fixtures.scenario()


class _FakeNessie:
    """Minimal stateful Nessie sandbox for MockTransport.

    Mirrors real-sandbox quirks seen at I4: account balances are stored as whole-dollar ints,
    PUT cannot change a balance, and TransferCreate rejects extra fields such as payee_id.
    """

    TRANSFER_FIELDS = {"transaction_date", "status", "amount", "description"}

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int, dict | None]] = []
        self.fail_delete_once = False
        self.customers: dict[str, dict] = {}
        self.accounts: dict[str, dict] = {}
        self.deposits: dict[str, list[dict]] = {}
        self.transfers: dict[str, list[dict]] = {}
        self.purchases: dict[str, list[dict]] = {}
        self.bills: dict[str, list[dict]] = {}
        self.merchants: dict[str, dict] = {}
        self._n = 0
        self.fail_5xx_once_paths: set[str] = set()
        self.always_5xx = False
        self.always_4xx = False

    def _id(self) -> str:
        self._n += 1
        return f"id-{self._n:04d}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        resp = self._handle(request)
        self.calls.append((request.method.upper(), request.url.path, resp.status_code,
                           json.loads(request.content.decode() or "null")))
        return resp

    def count(self, method: str | None = None) -> int:
        return sum(1 for m, *_ in self.calls if method in (None, m))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("key") == API_KEY
        path = request.url.path
        method = request.method.upper()
        if self.always_5xx or path in self.fail_5xx_once_paths:
            if path in self.fail_5xx_once_paths:
                self.fail_5xx_once_paths.discard(path)
            return httpx.Response(503, json={"message": "down"})
        if self.always_4xx:
            return httpx.Response(400, text=f"bad request key={API_KEY}")

        body = json.loads(request.content.decode() or "null")

        if method == "POST" and path == "/customers":
            cid = self._id()
            self.customers[cid] = {"_id": cid, **body}
            return httpx.Response(201, json={"objectCreated": self.customers[cid]})
        if method == "GET" and path == "/customers":
            return httpx.Response(200, json=list(self.customers.values()))
        if method == "GET" and path == "/accounts":
            return httpx.Response(200, json=list(self.accounts.values()))

        m = re.fullmatch(r"/customers/([^/]+)/accounts", path)
        if method == "POST" and m:
            aid = self._id()
            # Real sandbox truncates balance to an int.
            acct = {"_id": aid, "customer_id": m.group(1), **body, "balance": int(body.get("balance", 0))}
            self.accounts[aid] = acct
            self.deposits.setdefault(aid, [])
            self.transfers.setdefault(aid, [])
            self.purchases.setdefault(aid, [])
            self.bills.setdefault(aid, [])
            return httpx.Response(201, json={"objectCreated": acct})

        m = re.fullmatch(r"/accounts/([^/]+)", path)
        if method == "DELETE" and m:
            if self.fail_delete_once:
                self.fail_delete_once = False
                return httpx.Response(400, text="cannot delete")
            self.accounts.pop(m.group(1), None)  # real sandbox: 200 even if already gone
            return httpx.Response(200, json={"message": "deleted"})
        if method == "GET" and m:
            return httpx.Response(200, json=self.accounts[m.group(1)])

        m = re.fullmatch(r"/accounts/([^/]+)/deposits", path)
        if m:
            aid = m.group(1)
            if method == "GET":
                return httpx.Response(200, json=self.deposits[aid])
            dep = {"_id": self._id(), "amount": body["amount"], "description": body.get("description", ""),
                   "transaction_date": "2026-11-28", "status": body.get("status", "completed")}
            self.deposits.setdefault(aid, []).append(dep)
            # Mirror real sandbox: deposit posts do not mutate account.balance.
            return httpx.Response(201, json={"objectCreated": dep})

        m = re.fullmatch(r"/accounts/([^/]+)/transfers", path)
        if m:
            aid = m.group(1)
            if method == "GET":
                return httpx.Response(200, json=self.transfers.get(aid, []))
            extra = sorted(set(body) - self.TRANSFER_FIELDS)
            if extra:
                return httpx.Response(400, text=f"1 validation error for TransferCreate\n{extra[0]}\n"
                                                "  extra fields not permitted (type=value_error.extra)")
            tid = self._id()
            xfer = {"_id": tid, "payer_id": aid, "amount": body["amount"],
                    "description": body.get("description", ""), "status": body.get("status", "pending"),
                    "transaction_date": body.get("transaction_date", "2026-11-28")}
            self.transfers.setdefault(aid, []).append(xfer)
            return httpx.Response(201, json={"objectCreated": xfer})

        m = re.fullmatch(r"/transfers/([^/]+)", path)
        if method == "PUT" and m:
            tid = m.group(1)
            for lst in self.transfers.values():
                for x in lst:
                    if x["_id"] == tid:
                        x["status"] = body.get("status", x["status"])
                        return httpx.Response(200, json={"message": "Updated", "objectUpdated": x})
            return httpx.Response(404, text="missing")

        if method == "POST" and path == "/merchants":
            mid = self._id()
            self.merchants[mid] = {"_id": mid, **body}
            return httpx.Response(201, json={"objectCreated": self.merchants[mid]})

        m = re.fullmatch(r"/accounts/([^/]+)/purchases", path)
        if m:
            aid = m.group(1)
            if method == "GET":
                return httpx.Response(200, json=self.purchases[aid])
            pur = {"_id": self._id(), "amount": body["amount"], "description": body.get("description", ""),
                   "purchase_date": "2026-11-28", "merchant_id": body["merchant_id"]}
            self.purchases.setdefault(aid, []).append(pur)
            return httpx.Response(201, json={"objectCreated": pur})

        m = re.fullmatch(r"/accounts/([^/]+)/bills", path)
        if m:
            aid = m.group(1)
            if method == "GET":
                return httpx.Response(200, json=self.bills[aid])
            bill = {"_id": self._id(), "payee": body["payee"], "payment_amount": body["payment_amount"],
                    "payment_date": body.get("payment_date", "2026-11-28"), "status": body.get("status", "pending")}
            self.bills.setdefault(aid, []).append(bill)
            return httpx.Response(201, json={"objectCreated": bill})

        m = re.fullmatch(r"/bills/([^/]+)", path)
        if method == "PUT" and m:
            bid = m.group(1)
            for aid, lst in self.bills.items():
                for b in lst:
                    if b["_id"] == bid:
                        b["status"] = body.get("status", b["status"])
                        return httpx.Response(200, json={"message": "Updated"})
            return httpx.Response(404, text="missing")

        m = re.fullmatch(r"/accounts/([^/]+)/withdrawals", path)
        if method == "GET" and m:
            return httpx.Response(200, json=[])

        return httpx.Response(404, text=f"unhandled {method} {path}")


def _live(fake: _FakeNessie | None = None) -> tuple[LiveNessie, _FakeNessie]:
    fake = fake or _FakeNessie()
    transport = httpx.MockTransport(fake.handler)
    client = httpx.Client(transport=transport, base_url="http://nessie.test")
    n = LiveNessie(client=client, api_key=API_KEY, base_url="http://nessie.test")
    return n, fake


def test_live_requires_api_key(monkeypatch):
    monkeypatch.delenv("NESSIE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="NESSIE_API_KEY"):
        LiveNessie(api_key="")


def test_live_seed_creates_customer_account_deposit():
    n, fake = _live()
    n.seed(_scenario())
    assert set(n._accounts) == {"alex", "sam", "jordan"}
    assert len(fake.customers) == 3
    assert len(fake.accounts) == 3
    assert n.balance("alex") == 4200
    assert n.balance("sam") == 2600
    assert n.balance("jordan") == 310


def test_live_transfer_posts_and_moves_balances():
    n, fake = _live()
    n.seed(_scenario())
    sam_before = n._accounts["sam"]
    tid = n.transfer("sam", "alex", 800, "rent share")
    assert tid
    assert n.balance("sam") == 1800 and n.balance("alex") == 5000
    # Transfer was posted against the pre-recreate sam account id.
    posted = next(x for xs in fake.transfers.values() for x in xs if x["_id"] == tid)
    assert posted["payer_id"] == sam_before and posted["status"] == "completed"
    assert fake.accounts[n._accounts["sam"]]["balance"] == 1800
    assert fake.accounts[n._accounts["alex"]]["balance"] == 5000


def test_live_retry_once_on_5xx():
    n, fake = _live()
    n.seed(_scenario())
    fake.fail_5xx_once_paths.add(f"/accounts/{n._accounts['sam']}/transfers")
    assert n.transfer("sam", "alex", 800, "rent share")  # retried successfully
    assert n.balance("sam") == 1800


def test_live_persistent_5xx_raises_nessie_error():
    n, fake = _live()
    n.seed(_scenario())
    fake.always_5xx = True
    with pytest.raises(NessieError, match="503"):
        n.deposit("jordan", 1350, "Payroll deposit")
    assert n.balance("jordan") == 310  # ledger unchanged when the post fails


def test_live_4xx_raises_without_leaking_api_key():
    n, fake = _live()
    n.seed(_scenario())
    fake.always_4xx = True
    with pytest.raises(NessieError) as ei:
        n.deposit("jordan", 1, "x")
    assert API_KEY not in str(ei.value)


def test_live_unknown_rid_and_negative_amount():
    n, _ = _live()
    n.seed(_scenario())
    with pytest.raises(KeyError):
        n.balance("nobody")
    with pytest.raises(ValueError):
        n.transfer("sam", "alex", -5, "bad")


def test_live_pay_bill_and_purchase():
    n, _ = _live()
    n.seed(_scenario())
    n.pay_bill("alex", "Maple Court Apartments", 2400, "2026-11-28")
    n.purchase("alex", "Couch Co.", 1200, "couch")
    assert n.balance("alex") == 600  # 4200 - 2400 - 1200


# ----- I4 findings: cents, payee_id, reseed, call budget, logged swallows -----

def _sandbox_balances(n: LiveNessie, fake: _FakeNessie) -> dict[str, int]:
    return {rid: fake.accounts[aid]["balance"] for rid, aid in n._accounts.items()}


def test_live_cents_survive_couch_sequence():
    n, fake = _live()
    n.seed(_scenario())
    n.purchase("alex", "Couch Co.", 1200, "couch")
    n.transfer("sam", "alex", 133.33, "couch")
    n.transfer("jordan", "alex", 133.33, "couch")
    assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == (3266.66, 2466.67, 176.67)
    # The sandbox only holds whole dollars; it shows the floor of the exact ledger.
    assert _sandbox_balances(n, fake) == {"alex": 3266, "sam": 2466, "jordan": 176}


def test_live_negative_balance_floors_in_sandbox():
    n, fake = _live()
    n.seed(_scenario())
    n.transfer("jordan", "alex", 800.5, "rent")
    assert n.balance("jordan") == -490.5
    assert _sandbox_balances(n, fake)["jordan"] == -491


def test_live_transfer_never_sends_payee_id():
    n, fake = _live()
    n.seed(_scenario())
    n.transfer("sam", "alex", 800, "rent share")
    assert [c for c in fake.calls if c[2] >= 400] == []
    assert not any(isinstance(b, dict) and "payee_id" in b for *_, b in fake.calls)


def test_live_transfer_call_budget():
    n, fake = _live()
    n.seed(_scenario())
    before = len(fake.calls)
    n.transfer("sam", "alex", 800, "rent share")
    made = fake.calls[before:]
    assert len(made) <= 5, made
    assert not any(m in ("GET", "PUT") for m, *_ in made), made


def test_live_bill_purchase_deposit_skip_reads_and_puts():
    n, fake = _live()
    n.seed(_scenario())
    n.purchase("alex", "Couch Co.", 1, "warm merchant cache")
    before = len(fake.calls)
    n.pay_bill("alex", "Maple Court Apartments", 2400, "2026-11-28")
    n.purchase("alex", "Couch Co.", 1200, "couch")
    n.deposit("jordan", 1350, "Payroll deposit")
    made = fake.calls[before:]
    assert not any(m in ("GET", "PUT") for m, *_ in made), made
    assert len(made) == 9  # 3 x (POST object + DELETE + POST account)


def test_live_reseed_reuses_customers_one_account_each():
    n, fake = _live()
    n.seed(_scenario())
    n.transfer("sam", "alex", 800, "rent share")
    n.seed(_scenario())
    n.seed(_scenario())
    assert len(fake.customers) == 3
    per_customer: dict[str, int] = {}
    for a in fake.accounts.values():
        per_customer[a["customer_id"]] = per_customer.get(a["customer_id"], 0) + 1
    assert sorted(per_customer.values()) == [1, 1, 1]
    assert (n.balance("alex"), n.balance("sam"), n.balance("jordan")) == (4200, 2600, 310)
    assert _sandbox_balances(n, fake) == {"alex": 4200, "sam": 2600, "jordan": 310}
    assert n.transactions("alex") == []


def test_live_reseed_leaves_other_customers_alone():
    n, fake = _live()
    fake.customers["other"] = {"_id": "other", "first_name": "Alex", "last_name": "Roommate",
                               "address": {"street_name": "Elm Street"}}
    fake.accounts["other-acct"] = {"_id": "other-acct", "customer_id": "other", "balance": 99}
    n.seed(_scenario())
    n.seed(_scenario())
    assert fake.accounts["other-acct"]["balance"] == 99
    assert n._customers["alex"] != "other"


def test_live_swallowed_delete_failure_is_logged(caplog):
    n, fake = _live()
    n.seed(_scenario())
    fake.fail_delete_once = True
    with caplog.at_level("WARNING", logger="brain.nessie"):
        n.transfer("sam", "alex", 800, "rent share")
    assert n.balance("sam") == 1800  # the recreated account still carries the balance
    msgs = [r.getMessage() for r in caplog.records if r.name == "brain.nessie"]
    assert any("DELETE /accounts/" in m and "400" in m for m in msgs), msgs
    assert not any(API_KEY in m for m in msgs)
