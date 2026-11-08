"""Every result in fixtures/expected.json is a pytest assertion, on stub and real tools."""
import pytest

from app import fixtures, registry
from tests.conftest import impl_params

E = fixtures.expected()


@impl_params("tools")
@pytest.mark.parametrize("case", E.split_bill, ids=lambda c: c.bill_type)
def test_split_bill(use, mode, case):
    use(tools=mode)
    assert registry.get("tools").split_bill(case.bill_type, case.amount) == case.expect


def test_rent_share_is_800():
    assert E.rent_share == 800
    assert next(c for c in E.split_bill if c.bill_type == "rent").expect.shares == {
        "alex": 800, "sam": 800, "jordan": 800}


def test_electric_house_rule():
    assert next(c for c in E.split_bill if c.bill_type == "electric").expect.shares == {
        "sam": 60, "alex": 45, "jordan": 45}


@impl_params("tools")
@pytest.mark.parametrize("case", E.can_cover, ids=lambda c: f"{c.roommate_id}-{c.amount}")
def test_can_cover(use, mode, case):
    use(tools=mode)
    assert registry.get("tools").can_cover(case.roommate_id, case.amount, case.date) == case.expect


def test_jordan_cannot_cover_rent_until_payday():
    c = next(c for c in E.can_cover if c.roommate_id == "jordan" and c.amount == 800)
    assert (c.date, c.expect.level, c.expect.earliest_date) == ("2026-11-30", "no", "2026-12-15")


@impl_params("tools")
@pytest.mark.parametrize("case", E.payday_plan, ids=lambda c: c.roommate_id)
def test_payday_plan(use, mode, case):
    use(tools=mode)
    assert registry.get("tools").payday_plan(case.roommate_id, case.amount) == case.expect


@impl_params("tools")
@pytest.mark.parametrize("case", E.group_affordability, ids=lambda c: c.item)
def test_group_affordability(use, mode, case):
    use(tools=mode)
    got = registry.get("tools").group_affordability(case.item, case.price)
    assert got == case.expect
    assert got.plan.months == 3 and got.answers["jordan"] == "tight"
