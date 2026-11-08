import pytest

from app import fixtures, registry
from tests.conftest import impl_params

KEYS = {"emergency_fund_months", "debt_to_income", "savings_rate", "credit_utilization", "net_worth",
        "debt_to_asset", "housing_cost_ratio", "liquidity_ratio",
        "runway_days", "rent_to_income", "days_to_payday", "buffer_after"}


@impl_params("indicators")
@pytest.mark.parametrize("rid", ["alex", "sam", "jordan"])
def test_indicators_match_expected(use, mode, rid):
    use(indicators=mode)
    got = registry.get("indicators").compute(rid)
    assert set(got) == KEYS
    want = fixtures.expected().indicators[rid]
    for k in KEYS:
        assert got[k].value == pytest.approx(want[k].value, abs=0.01), k
        assert got[k].status == want[k].status, k


@impl_params("indicators")
def test_jordan_runway_under_two_weeks(use, mode):
    use(indicators=mode)
    ind = registry.get("indicators").compute("jordan")
    assert ind["runway_days"].value < 14
    assert ind["buffer_after"].inputs["amount"] == 800
