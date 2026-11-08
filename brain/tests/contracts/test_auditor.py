import pytest

from app import fixtures, registry
from tests.conftest import impl_params

RENT = fixtures.expected().scripts.rent_group


@impl_params("auditor")
def test_correct_rent_message_passes(use, mode):
    use(auditor=mode)
    assert registry.get("auditor").check(RENT, {2400, 800}, "group").ok


@impl_params("auditor")
def test_jordans_balance_blocked_in_group(use, mode):
    if mode == "stub":
        pytest.skip("stub auditor always passes")
    use(auditor=mode)
    a = registry.get("auditor")
    res = a.check("Jordan only has $310, so Alex fronts $800.", {800, 310}, "group")
    assert not res.ok and any("310" in r for r in res.reasons)
    assert not a.check("That's $999 each.", {800}, "group").ok        # invented number
    assert a.check("Your balance is $310.", {310}, "jordan").ok       # own numbers in own DM
