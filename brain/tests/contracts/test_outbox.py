from contracts.models import GroupTarget, Reply

from app import registry


def test_stub_outbox_collects():
    r = Reply(target=GroupTarget(), text="hi")
    registry.get("outbox").send(r)
    assert registry.get("outbox").sent == [r]
