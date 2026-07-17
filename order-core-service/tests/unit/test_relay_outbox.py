"""Тесты сценария-реле outbox (на фейках)."""

import uuid

from app.application.dto import PendingEvent
from app.application.relay_outbox import RelayOutbox
from tests.fakes import FakeEventPublisher, FakeLogger, FakeOutboxDispatchFactory


def _event(destination: str) -> PendingEvent:
    return PendingEvent(id=uuid.uuid4(), destination=destination, payload={"k": "v"})


async def test_publishes_marks_and_commits_pending() -> None:
    factory = FakeOutboxDispatchFactory([_event("assess_request"), _event("notify")])
    publisher = FakeEventPublisher()

    count = await RelayOutbox(
        dispatch_factory=factory, publisher=publisher, batch_size=10, logger=FakeLogger()
    ).run_once()

    assert count == 2
    assert [dest for dest, _ in publisher.published] == ["assess_request", "notify"]
    assert len(factory.published_ids) == 2
    assert factory.committed_count == 1
    assert factory.pending == []


async def test_empty_batch_is_noop() -> None:
    factory = FakeOutboxDispatchFactory([])
    publisher = FakeEventPublisher()

    count = await RelayOutbox(
        dispatch_factory=factory, publisher=publisher, batch_size=10, logger=FakeLogger()
    ).run_once()

    assert count == 0
    assert publisher.published == []
    assert factory.committed_count == 0
