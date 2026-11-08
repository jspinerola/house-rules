from contracts.models import Ask, Release

from app import registry
from tests.conftest import impl_params


@impl_params("personal")
def test_jordan_release_is_level_and_date_only(use, mode):
    use(personal=mode)
    rel = registry.get("personal").ask("jordan", Ask(amount=800, by_date="2026-11-30", purpose="rent"))
    assert isinstance(rel, Release)
    assert rel.model_dump() == {"level": "no", "earliest_date": "2026-12-15"}


@impl_params("personal")
def test_dm_goes_to_that_roommate(use, mode):
    use(personal=mode)
    replies = registry.get("personal").dm("sam", "what's my runway?")
    assert replies and all(r.target.type == "dm" and r.target.roommate_id == "sam" for r in replies)


@impl_params("personal")
def test_jordan_dm_explains_fronting(use, mode):
    use(personal=mode)
    registry.get("house").on_event("rent_due")
    p = registry.get("store").proposals()[0]
    replies = registry.get("personal").explain("jordan", p)
    assert replies and "Alex" in replies[0].text and "2026-12-16" in replies[0].text
