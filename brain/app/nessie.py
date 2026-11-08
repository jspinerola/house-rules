"""Live Nessie client (NESSIE_MODE=live).

Uses Capital One Nessie REST endpoints. Injectable httpx.Client supports
MockTransport unit tests; production uses env NESSIE_API_KEY / NESSIE_BASE_URL.

Sandbox quirks this client works around (confirmed live at checkpoint I4):
- Account balances are whole-dollar ints, and PUT /accounts ignores `balance`. Posting a
  transfer/deposit/purchase/bill does not move account.balance either. So after each move we
  recreate the checking account with the new balance (REQUIREMENTS M9 done-when).
- Because the sandbox drops cents, this client keeps the exact balance in its own ledger
  (integer cents). `balance()` and `/bank` read that ledger; Nessie shows the floored dollars.
- TransferCreate rejects extra fields (`payee_id`, `medium`), so transfers post the payer side
  only; the payee is named in the description.
- Customers cannot be deleted, so `seed` reuses the House Rules customers it finds on the key
  and deletes their old accounts instead of creating new customers on every reset.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from contracts.interfaces import NessieError
from contracts.models import BankTxn, Scenario

from . import config

log = logging.getLogger("brain.nessie")

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


def _cents(amount: float) -> int:
    return round(amount * 100)


def _created(payload: dict) -> dict:
    return payload.get("objectCreated") or payload


def _split_name(name: str) -> tuple[str, str]:
    parts = name.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else "Roommate")


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
        self._ledger: dict[str, int] = {}  # exact balance in cents; Nessie only keeps dollars

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

    def _create_account(self, rid: str) -> str:
        cid = self._customers[rid]
        acct = _created(self._request("POST", f"/customers/{cid}/accounts", {
            "type": "Checking",
            "nickname": f"{self._names.get(rid, rid)} Checking",
            "rewards": 0,
            "balance": self._ledger[rid] // 100,  # whole dollars, floored
        }))
        aid = str(acct["_id"])
        self._accounts[rid] = aid
        return aid

    def _delete_account(self, aid: str) -> None:
        try:
            self._request("DELETE", f"/accounts/{aid}")
        except NessieError as e:
            # The replacement account carries the balance, so a stale account is cosmetic.
            log.warning("nessie DELETE /accounts/%s ignored: %s", aid, e)

    def _sync_balance(self, rid: str) -> None:
        """Mirror the ledger into Nessie by recreating the checking account (sandbox quirk)."""
        old = self._accounts.get(rid)
        if old:
            self._delete_account(old)
        self._create_account(rid)

    def _move(self, rid: str, amount: float) -> None:
        self._ledger[rid] += _cents(amount)
        self._sync_balance(rid)

    def _remember(self, rid: str, nid: str, amount: float, description: str) -> None:
        self._txns.setdefault(rid, []).append(BankTxn(
            id=nid, date=self._today(), description=description, amount=round(amount, 2)))

    def _house_customers(self) -> dict[tuple[str, str], list[str]]:
        """Customers on this key created by House Rules, keyed by (first, last) name."""
        found: dict[tuple[str, str], list[str]] = {}
        for c in self._request("GET", "/customers"):
            if (c.get("address") or {}).get("street_name") == _DEFAULT_ADDRESS["street_name"]:
                found.setdefault((c.get("first_name"), c.get("last_name")), []).append(str(c["_id"]))
        return found

    def seed(self, scenario: Scenario) -> None:
        self._customers.clear()
        self._accounts.clear()
        self._merchants.clear()
        self._txns.clear()
        self._ledger.clear()
        self._names = {r.id: r.name for r in scenario.roommates}

        existing = self._house_customers()
        ours = {cid for r in scenario.roommates for cid in existing.get(_split_name(r.name), [])}
        for a in self._request("GET", "/accounts"):
            if str(a.get("customer_id")) in ours:
                self._delete_account(str(a["_id"]))

        for r in scenario.roommates:
            first, last = _split_name(r.name)
            matches = existing.get((first, last))
            if matches:
                self._customers[r.id] = matches[0]
            else:
                cust = _created(self._request("POST", "/customers", {
                    "first_name": first, "last_name": last, "address": _DEFAULT_ADDRESS,
                }))
                self._customers[r.id] = str(cust["_id"])
            self._txns[r.id] = []
            self._ledger[r.id] = _cents(r.checking)
            self._create_account(r.id)

    def balance(self, rid: str) -> float:
        self._account(rid)  # unknown rid -> KeyError
        return self._ledger[rid] / 100

    def transactions(self, rid: str) -> list[BankTxn]:
        self._account(rid)  # unknown rid -> KeyError
        return sorted(self._txns.get(rid, []), key=lambda t: (t.date, t.id), reverse=True)

    def transfer(self, from_rid: str, to_rid: str, amount: float, description: str) -> str:
        amount = _money(amount)
        from_id = self._account(from_rid)
        self._account(to_rid)
        to_name = self._names.get(to_rid, to_rid)
        created = _created(self._request("POST", f"/accounts/{from_id}/transfers", {
            "transaction_date": self._today(),
            "status": "completed",
            "amount": amount,
            "description": f"To {to_name}: {description}",
        }))
        tid = str(created["_id"])
        self._move(from_rid, -amount)
        self._move(to_rid, amount)
        self._remember(from_rid, tid, -amount, f"Transfer to {to_name}: {description}")
        self._remember(to_rid, tid, amount, f"Transfer from {self._names.get(from_rid, from_rid)}: {description}")
        return tid

    def deposit(self, rid: str, amount: float, description: str, on: str | None = None) -> str:
        amount = _money(amount)
        created = _created(self._request("POST", f"/accounts/{self._account(rid)}/deposits", {
            "medium": "balance",
            "transaction_date": on or self._today(),
            "status": "completed",
            "amount": amount,
            "description": description,
        }))
        nid = str(created["_id"])
        self._move(rid, amount)
        self._remember(rid, nid, amount, description)
        return nid

    def pay_bill(self, rid: str, payee: str, amount: float, date: str) -> str:
        amount = _money(amount)
        created = _created(self._request("POST", f"/accounts/{self._account(rid)}/bills", {
            "status": "completed",
            "payee": payee,
            "nickname": payee,
            "payment_date": date,
            "recurring_date": 1,
            "payment_amount": amount,
        }))
        bid = str(created["_id"])
        self._move(rid, -amount)
        self._remember(rid, bid, -amount, f"Bill payment - {payee}")
        return bid

    def purchase(self, rid: str, merchant: str, amount: float, description: str) -> str:
        amount = _money(amount)
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
        self._move(rid, -amount)
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
