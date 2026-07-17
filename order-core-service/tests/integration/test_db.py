"""Интеграционные тесты БД против реального PostgreSQL (нужен POSTGRES_TEST_URL).

Проверяют то, что нельзя проверить на фейках: реальные уникальные ограничения,
`ON CONFLICT DO NOTHING`, транзакции и сквозной путь сценариев на настоящей БД.
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.dto import IncomingOrder
from app.application.ingest_orders import IngestOrders
from app.application.process_assessment import ProcessAssessment
from app.domain.assessment import AssessmentOutcome
from app.domain.notification import NotificationCommand
from app.domain.source import Source
from app.domain.status import OrderStatus
from app.infrastructure.db.models import OrderRow, OutboxRow
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from tests.fakes import FakeLogger

pytestmark = pytest.mark.postgres


def _order(ext: str) -> IncomingOrder:
    return IncomingOrder(
        source=Source.PROFI, external_id=ext, payload={"id": ext, "title": "t"}, request_id="r"
    )


async def test_insert_new_deduplicates_on_unique_constraint(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    async with uow_factory() as uow:
        assert await uow.orders.insert_new(_order("1")) is True
        assert await uow.orders.insert_new(_order("1")) is False  # конфликт (source, external_id)
        await uow.commit()

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(OrderRow))
    assert count == 1


async def test_set_status_and_get_roundtrip(uow_factory: SqlAlchemyUnitOfWorkFactory) -> None:
    async with uow_factory() as uow:
        await uow.orders.insert_new(_order("1"))
        await uow.commit()

    async with uow_factory() as uow:
        changed = await uow.orders.set_status(
            Source.PROFI, "1", OrderStatus.NOTIFY_REQUESTED, 90
        )
        assert changed is True
        await uow.commit()

    async with uow_factory() as uow:
        order = await uow.orders.get(Source.PROFI, "1")
    assert order is not None
    assert order.status is OrderStatus.NOTIFY_REQUESTED
    assert order.suitability_score == 90


async def test_outbox_dedup_key_is_unique(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    async with uow_factory() as uow:
        await uow.outbox.add_assessment_request(_order("1"))
        await uow.outbox.add_assessment_request(_order("1"))  # тот же dedup_key
        await uow.commit()

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(OutboxRow))
    assert count == 1


async def test_rollback_discards_changes(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    async with uow_factory() as uow:
        await uow.orders.insert_new(_order("1"))
        await uow.rollback()

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(OrderRow))
    assert count == 0


async def test_ingest_then_process_persists_state_and_outbox(
    uow_factory: SqlAlchemyUnitOfWorkFactory, session_factory: async_sessionmaker
) -> None:
    await IngestOrders(uow_factory=uow_factory, logger=FakeLogger()).handle([_order("1")])
    await ProcessAssessment(uow_factory=uow_factory, threshold=0, logger=FakeLogger()).handle(
        AssessmentOutcome(
            order_id="1", suitability_score=90, notification=NotificationCommand(text="t")
        )
    )

    async with session_factory() as session:
        order = await session.scalar(select(OrderRow).where(OrderRow.external_id == "1"))
        assert order is not None
        assert order.status == OrderStatus.NOTIFY_REQUESTED.value
        assert order.suitability_score == 90
        rows = (await session.scalars(select(OutboxRow))).all()

    assert sorted(row.destination for row in rows) == ["assess_request", "notify"]
