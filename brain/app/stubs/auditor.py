from __future__ import annotations

from contracts.models import AuditResult


class StubAuditor:
    def check(self, text: str, allowed_numbers: set[float], audience: str) -> AuditResult:
        return AuditResult(ok=True)
