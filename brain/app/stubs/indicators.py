"""Fixed indicator values from fixtures/expected.json."""
from __future__ import annotations

from contracts.models import Indicator

from .. import fixtures


class StubIndicators:
    def compute(self, rid: str) -> dict[str, Indicator]:
        return {k: v.model_copy() for k, v in fixtures.expected().indicators[rid].items()}
