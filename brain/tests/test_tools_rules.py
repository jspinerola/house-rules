"""Edge cases of the real tools beyond expected.json."""
import pytest

from app import registry


@pytest.fixture
def tools(use):
    use(tools="real")
    return registry.get("tools")


def test_next_payday_rules(tools):
    assert tools.next_payday("alex", "2026-12-01") == "2027-01-01"
    assert tools.next_payday("alex", "2026-12-31") == "2027-01-01"
    assert tools.next_payday("sam", "2026-12-05") == "2026-12-19"
    assert tools.next_payday("sam", "2026-11-21") == "2026-12-05"
    assert tools.next_payday("jordan", "2026-12-14") == "2026-12-15"


def test_split_rounding_cents_land_on_one_person(tools):
    shares = tools.split_bill("water", 100).shares
    assert round(sum(shares.values()), 2) == 100 and sorted(shares.values()) == [33.33, 33.33, 33.34]


def test_cover_counts_paydays_before_the_date(tools):
    # After Jordan's 12-15 paycheck, $800 is coverable.
    assert tools.can_cover("jordan", 800, "2026-12-15").level != "no"


def test_committed_legs_reduce_cover(tools):
    from contracts.models import Leg
    registry.get("proposals").create("rent", "Rent", [
        Leg(type="transfer", **{"from": "sam"}, to="alex", amount=2500, date="2026-11-28")], ["sam"])
    assert tools.can_cover("sam", 0, "2026-11-28").level == "tight"
