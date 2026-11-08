"""Live Nessie client (NESSIE_MODE=live).

Uses Capital One Nessie REST endpoints. Injectable httpx.Client supports
MockTransport unit tests; production uses env NESSIE_API_KEY / NESSIE_BASE_URL.

The current Nessie sandbox accepts transfer/deposit/purchase posts but often does
not mutate account.balance. We still POST those objects for nessie_ids, then
recreate the checking account with the updated balance so GET /accounts reflects
the move (REQUIREMENTS M9 done-when).
"""
from __future__ import annotations

import math
from typing import Any

import httpx

from contracts.interfaces import NessieError
from contracts.models import BankTxn, Scenario

from . import config

_DEFAULT_ADDRESS = {
    "street_number": "1",
    "street_name": "Maple Court",
    "city": "Dallas",
    "state": "TX",
    "zip": "75201",
}


def _money(amount: float, label: str = "amount") -> float:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not math.isfinite(amount):
        raise ValueError(f"{label} must be a finite number")
    if amount < 0:
        raise ValueError(f"{label} must be >= 0")
    return float(amount)


def _created(payload: dict) -> dict:
    return payload.get("objectCreated") or payload


class LiveNessie:
    def __init__(
        self,
        client: httpx.Client | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else config.nessie_api_key()).strip()
        if not self.api_key:
            raise ValueError("NESSIE_API_KEY is required for NESSIE_MODE=live")
        self.base_url = (base_url or config.nessie_base_url()).rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=30.0)
        self._customers: dict[str, str] = {}
        self._accounts: dict[str, str] = {}
        self._merchants: dict[str, str] = {}
        self._names: dict[str, str] = {}
        self._txns: dict[str, list[BankTxn]] = {}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _account(self, rid: str) -> str:
        if rid not in self._accounts:
            raise KeyError(f"unknown roommate {rid!r}; call seed() first")
        return self._accounts[rid]

    def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        params = {"key": self.api_key}
        body = None if json is None else {k: v for k, v in json.items() if v is not None}
        last: httpx.Response | None = None
        for attempt in range(2):
            try:
                last = self._client.request(method, url, params=params, json=body)
            except httpx.HTTPError as e:
                raise NessieError(f"Nessie {method} {path} network error") from e
            if last.status_code >= 500 and attempt == 0:
                continue
            break
        assert last is not None
        if last.status_code >= 400:
            detail = (last.text or "")[:200].replace(self.api_key, "***")
            raise NessieError(f"Nessie {method} {path} failed ({last.status_code}): {detail}")
        if not last.content:
            return {}
        try:
            return last.json()
        except ValueError as e:
            raise NessieError(f"Nessie {method} {path} returned non-JSON") from e

    def _today(self) -> str:
        try:
            from . import registry
            return registry.get("store").today()
        except Exception:
            return "2026-11-28"

    def _create_account(self, rid: str, balance: float) -> str:
        cid = self._customers[rid]
        acct = _created(self._request("POST", f"/customers/{cid}/accounts", {
            "type": "Checking",
            "nickname": f"{self._names.get(rid, rid)} Checking",
            "rewards": 0,
            "balance": round(balance, 2),
        }))
        aid = str(acct["_id"])
        self._accounts[rid] = aid
        return aid

    def _set_balance(self, rid: str, balance: float) -> None:
        """Persist balance in Nessie by recreating the checking account (sandbox quirk)."""
        old = self._accounts.get(rid)
        if old:
            try:
                self._request("DELETE", f"/accounts/{old}")
            except NessieError:
                pass
        self._create_account(rid, balance)

    def _remember(self, rid: str, nid: str, amount: float, description: str) -> None:
        self._txns.setdefault(rid, []).append(BankTxn(
            id=nid, date=self._today(), description=description, amount=round(amount, 2)))

    def seed(self, scenario: Scenario) -> None:
        self._customers.clear()
        self._accounts.clear()
        self._merchants.clear()
        self._txns.clear()
        self._names = {r.id: r.name for r in scenario.roommates}
        for r in scenario.roommates:
            parts = r.name.split(None, 1)
            first, last = parts[0], (parts[1] if len(parts) > 1 else "Roommate")
            cust = _created(self._request("POST", "/customers", {
                "first_name": first, "last_name": last, "address": _DEFAULT_ADDRESS,
            }))
            self._customers[r.id] = str(cust["_id"])
            self._txns[r.id] = []
            self._create_account(r.id, r.checking)

    def balance(self, rid: str) -> float:
        acct = self._request("GET", f"/accounts/{self._account(rid)}")
        return float(acct["balance"])

    def transactions(self, rid: str) -> list[BankTxn]:
        self._account(rid)  # unknown rid -> KeyError
        return sorted(self._txns.get(rid, []), key=lambda t: (t.date, t.id), reverse=True)

    def transfer(self, from_rid: str, to_rid: str, amount: float, description: str) -> str:
        amount = _money(amount)
        from_id, to_id = self._account(from_rid), self._account(to_rid)
        from_bal = self.balance(from_rid) - amount
        to_bal = self.balance(to_rid) + amount
        # Sandbox TransferCreate often rejects payee_id; still post for an id when possible.
        try:
            created = _created(self._request("POST", f"/accounts/{from_id}/transfers", {
                "transaction_date": self._today(),
                "status": "pending",
                "amount": amount,
                "description": description,
                "payee_id": to_id,
            }))
            tid = str(created["_id"])
            if created.get("status") == "pending":
                try:
                    self._request("PUT", f"/transfers/{tid}", {"status": "completed"})
                except NessieError:
                    pass
        except NessieError:
            created = _created(self._request("POST", f"/accounts/{from_id}/transfers", {
                "transaction_date": self._today(),
                "status": "pending",
                "amount": amount,
                "description": description,
            }))
            tid = str(created["_id"])
        self._set_balance(from_rid, from_bal)
        self._set_balance(to_rid, to_bal)
        self._remember(from_rid, tid, -amount, f"Transfer to {self._names.get(to_rid, to_rid)}: {description}")
        self._remember(to_rid, tid, amount, f"Transfer from {self._names.get(from_rid, from_rid)}: {description}")
        return tid

    def deposit(self, rid: str, amount: float, description: str, on: str | None = None) -> str:
        amount = _money(amount)
        new_bal = self.balance(rid) + amount
        created = _created(self._request("POST", f"/accounts/{self._account(rid)}/deposits", {
            "medium": "balance",
            "transaction_date": on or self._today(),
            "status": "completed",
            "amount": amount,
            "description": description,
        }))
        nid = str(created["_id"])
        self._set_balance(rid, new_bal)
        self._remember(rid, nid, amount, description)
        return nid

    def pay_bill(self, rid: str, payee: str, amount: float, date: str) -> str:
        amount = _money(amount)
        new_bal = self.balance(rid) - amount
        created = _created(self._request("POST", f"/accounts/{self._account(rid)}/bills", {
            "status": "pending",
            "payee": payee,
            "nickname": payee,
            "payment_date": date,
            "recurring_date": 1,
            "payment_amount": amount,
        }))
        bid = str(created["_id"])
        try:
            self._request("PUT", f"/bills/{bid}", {"status": "completed"})
        except NessieError:
            pass
        self._set_balance(rid, new_bal)
        self._remember(rid, bid, -amount, f"Bill payment - {payee}")
        return bid

    def purchase(self, rid: str, merchant: str, amount: float, description: str) -> str:
        amount = _money(amount)
        new_bal = self.balance(rid) - amount
        mid = self._merchant_id(merchant)
        created = _created(self._request("POST", f"/accounts/{self._account(rid)}/purchases", {
            "merchant_id": mid,
            "medium": "balance",
            "purchase_date": self._today(),
            "amount": amount,
            "status": "completed",
            "description": description,
        }))
        nid = str(created["_id"])
        self._set_balance(rid, new_bal)
        self._remember(rid, nid, -amount, f"Purchase - {merchant}: {description}")
        return nid

    def _merchant_id(self, name: str) -> str:
        if name in self._merchants:
            return self._merchants[name]
        created = _created(self._request("POST", "/merchants", {
            "name": name,
            "category": "house_rules",
            "address": _DEFAULT_ADDRESS,
            "geocode": {"lat": 32.78, "lng": -96.8},
        }))
        mid = str(created["_id"])
        self._merchants[name] = mid
        return mid
