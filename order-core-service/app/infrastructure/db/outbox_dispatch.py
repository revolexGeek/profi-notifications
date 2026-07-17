"""Транзакционный клейм outbox для реле — FOR UPDATE SKIP LOCKED.

Блокирует батч pending-строк на время транзакции (другие инстансы реле их
пропускают), реле публикует их и помечает published; commit снимает блокировку.
"""

import uuid
from types import TracebackType

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.dto import PendingEvent
from app.infrastructure.db.models import OutboxRow


class SqlAlchemyOutboxDispatch:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyOutboxDispatch":
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            if exc_type is not None:
                await session.rollback()
        finally:
            await session.close()
            self._session = None

    async def claim_pending(self, limit: int) -> list[PendingEvent]:
        session = self._require_session()
        rows = (
            await session.scalars(
                select(OutboxRow)
                .where(OutboxRow.status == "pending")
                .order_by(OutboxRow.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        return [
            PendingEvent(id=row.id, destination=row.destination, payload=row.payload)
            for row in rows
        ]

    async def mark_published(self, ids: list[uuid.UUID]) -> None:
        if not ids:
            return
        session = self._require_session()
        await session.execute(
            update(OutboxRow)
            .where(OutboxRow.id.in_(ids))
            .values(status="published", published_at=func.now())
        )

    async def commit(self) -> None:
        await self._require_session().commit()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("OutboxDispatch используется вне своего контекста")
        return self._session


class SqlAlchemyOutboxDispatchFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyOutboxDispatch:
        return SqlAlchemyOutboxDispatch(self._session_factory)
