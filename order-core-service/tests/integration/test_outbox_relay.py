"""Интеграционные тесты outbox-реле: реальная БД (FOR UPDATE SKIP LOCKED) + брокер."""

from typing import Any, cast

import pytest
from faststream.rabbit import RabbitBroker, TestRabbitBroker
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.dto import IncomingOrder
from app.application.relay_outbox import RelayOutbox
from app.domain.notification import NotificationCommand
from app.domain.source import Source
from app.infrastructure.db.models import OutboxRow
from app.infrastructure.db.outbox_dispatch import SqlAlchemyOutboxDispatchFactory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.messaging.broker import (
    build_assess_request_publisher,
    build_notify_publisher,
)
from app.infrastructure.messaging.event_publisher import FastStreamEventPublisher
from tests.fakes import FakeLogger

pytestmark = pytest.mark.postgres


def _build_relay(session_factory: async_sessionmaker, broker: RabbitBroker) -> RelayOutbox:
    publisher = FastStreamEventPublisher(
        assess_request=build_assess_request_publisher(broker, queue="assess.requests"),
        notify=build_notify_publisher(broker, exchange="notifications", routing_key="notify"),
    )
    return RelayOutbox(
        dispatch_factory=SqlAlchemyOutboxDispatchFactory(session_factory),
        publisher=publisher,
        batch_size=10,
        logger=FakeLogger(),
    )


async def _seed_two_events(uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
    async with uow_factory() as uow:
        await uow.outbox.add_assessment_request(
            IncomingOrder(source=Source.PROFI, external_id="1", payload={"id": "1"})
        )
        await uow.outbox.add_notification(
            Source.PROFI, "1", NotificationCommand(text="hi", parse_mode="HTML")
        )
        await uow.commit()


async def test_relay_publishes_pending_and_marks_them(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    await _seed_two_events(uow_factory)
    broker = RabbitBroker()
    assess_pub = build_assess_request_publisher(broker, queue="assess.requests")
    notify_pub = build_notify_publisher(broker, exchange="notifications", routing_key="notify")
    publisher = FastStreamEventPublisher(assess_request=assess_pub, notify=notify_pub)
    relay = RelayOutbox(
        dispatch_factory=SqlAlchemyOutboxDispatchFactory(session_factory),
        publisher=publisher,
        batch_size=10,
        logger=FakeLogger(),
    )

    async with TestRabbitBroker(broker):
        count = await relay.run_once()
        assert count == 2
        cast(Any, assess_pub).mock.assert_called_once()
        cast(Any, notify_pub).mock.assert_called_once()
        notify_payload = cast(Any, notify_pub).mock.call_args.args[0]
        assert notify_payload["text"] == "hi"
        assert notify_payload["parseMode"] == "HTML"

    async with session_factory() as session:
        pending = await session.scalar(
            select(func.count()).select_from(OutboxRow).where(OutboxRow.status == "pending")
        )
    assert pending == 0


async def test_relay_second_run_is_noop(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    await _seed_two_events(uow_factory)
    broker = RabbitBroker()
    relay = _build_relay(session_factory, broker)

    async with TestRabbitBroker(broker):
        assert await relay.run_once() == 2
        assert await relay.run_once() == 0  # уже опубликовано
