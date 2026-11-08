"""Live Nessie client (NESSIE_MODE=live) lands in D2.

Confirm endpoint names in the Nessie docs first: POST /customers, /customers/{id}/accounts,
/accounts/{id}/transfers, /accounts/{id}/bills, /accounts/{id}/purchases, /accounts/{id}/deposits.
Must satisfy contracts.interfaces.Nessie, retry once on 5xx, and raise NessieError on failure.
The skeleton never calls the real API.
"""
from __future__ import annotations


class LiveNessie:
    def __init__(self) -> None:
        raise NotImplementedError("NESSIE_MODE=live is not implemented yet (D2); use NESSIE_MODE=stub")
