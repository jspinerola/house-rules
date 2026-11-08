from contracts.models import Affordability, CoverAnswer, PaydayPlan, SplitResult

from app import registry
from tests.conftest import impl_params


@impl_params("tools")
def test_tools_contract_shapes(use, mode):
    use(tools=mode)
    t = registry.get("tools")
    assert isinstance(t.split_bill("rent", 2400), SplitResult)
    assert isinstance(t.can_cover("alex", 800, "2026-11-30"), CoverAnswer)
    assert isinstance(t.payday_plan("jordan", 800), PaydayPlan)
    assert isinstance(t.group_affordability("couch", 1200), Affordability)
    assert t.next_payday("jordan", "2026-11-28") == "2026-12-15"
    assert t.next_payday("sam", "2026-11-28") == "2026-12-05"
