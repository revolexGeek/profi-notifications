"""Репозитории поверх SQLAlchemy async — реализации портов приложения.

Дедуп и идемпотентность событий держатся на БД: `INSERT ... ON CONFLICT DO
NOTHING` по `(source, external_id)` и по `outbox.dedup_key`. Факт вставки/
обновления определяем через `RETURNING` (portable-типизация без `rowcount`).
"""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto import IncomingOrder
from app.domain.notification import NotificationCommand
from app.domain.order import Order
from app.domain.source import Source
from app.domain.status import OrderStatus
from app.infrastructure.db.models import OrderRow, OutboxDestination, OutboxRow
from app.infrastructure.messaging.mapping import assess_request_payload, notification_payload


class SqlAlchemyOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_new(self, order: IncomingOrder) -> bool:
        stmt = (
            pg_insert(OrderRow)
            .values(
                source=str(order.source),
                external_id=order.external_id,
                status=OrderStatus.ASSESS_REQUESTED.value,
                payload=order.payload,
                request_id=order.request_id,
                source_fetched_at=order.fetched_at,
            )
            .on_conflict_do_nothing(index_elements=["source", "external_id"])
            .returning(OrderRow.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get(self, source: Source, external_id: str) -> Order | None:
        row = await self._session.scalar(
            select(OrderRow).where(
                OrderRow.source == str(source), OrderRow.external_id == external_id
            )
        )
        if row is None:
            return None
        return Order(
            source=Source(row.source),
            external_id=row.external_id,
            status=OrderStatus(row.status),
            suitability_score=row.suitability_score,
        )

    async def set_status(
        self,
        source: Source,
        external_id: str,
        status: OrderStatus,
        suitability_score: int | None,
    ) -> bool:
        stmt = (
            update(OrderRow)
            .where(OrderRow.source == str(source), OrderRow.external_id == external_id)
            .values(status=status.value, suitability_score=suitability_score)
            .returning(OrderRow.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class SqlAlchemyOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_assessment_request(self, order: IncomingOrder) -> None:
        await self._add(
            OutboxDestination.ASSESS_REQUEST,
            f"assess:{order.source}:{order.external_id}",
            assess_request_payload(order),
        )

    async def add_notification(
        self, source: Source, external_id: str, notification: NotificationCommand
    ) -> None:
        await self._add(
            OutboxDestination.NOTIFY,
            f"notify:{source}:{external_id}",
            notification_payload(notification),
        )

    async def _add(
        self, destination: OutboxDestination, dedup_key: str, payload: dict[str, Any]
    ) -> None:
        stmt = (
            pg_insert(OutboxRow)
            .values(destination=destination.value, dedup_key=dedup_key, payload=payload)
            .on_conflict_do_nothing(index_elements=["dedup_key"])
        )
        await self._session.execute(stmt)
