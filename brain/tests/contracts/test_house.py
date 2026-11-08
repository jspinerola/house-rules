from app import registry
from tests.conftest import impl_params


@impl_params("house")
def test_rent_due_proposes_fronting(use, mode):
    use(house=mode)
    replies = registry.get("house").on_event("rent_due")
    assert any(r.target.type == "group" for r in replies)
    [p] = registry.get("store").proposals()
    assert p.flow == "rent" and set(p.required_approvers) == {"alex", "sam", "jordan"}
    summary = {(l.type, l.from_, l.to or l.payee, l.amount, l.date) for l in p.legs}
    assert summary == {("transfer", "sam", "alex", 800, "2026-11-28"),
                       ("bill_payment", "alex", "Maple Court Apartments", 2400, "2026-11-28"),
                       ("scheduled_transfer", "jordan", "alex", 800, "2026-12-16")}


@impl_params("house")
def test_couch_asks_three_and_proposes_three_months(use, mode):
    use(house=mode)
    replies = registry.get("house").on_message("alex", "can we afford a $1,200 couch?")
    assert replies and "3 months" in replies[0].text
    asked = [e for e in registry.get("store").recent_trace() if e.agent == "house" and e.event == "asked"]
    assert len(asked) == 3
    [p] = registry.get("store").proposals()
    assert p.flow == "purchase"
    assert sum(l.amount for l in p.legs if l.type == "purchase") == 1200
    installments = [l for l in p.legs if l.type == "scheduled_transfer"]
    assert len(installments) == 6 and round(sum(l.amount for l in installments), 2) == 800
