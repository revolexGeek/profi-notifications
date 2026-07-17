"""Выходные порты приложения (реализуются в infrastructure).

Домен и сценарии зависят только от этих интерфейсов — конкретные адаптеры
(PostgreSQL, RabbitMQ, логгер) подставляются в composition root.
"""

import uuid
from types import TracebackType
from typing import Any, Protocol

from app.application.dto import IncomingOrder, PendingEvent
from app.domain.notification import NotificationCommand
from app.domain.order import Order
from app.domain.source import Source
from app.domain.status import OrderStatus


class OrderRepository(Protocol):
    async def insert_new(self, order: IncomingOrder) -> bool:
        """Вставляет новую заявку; `False`, если такая уже есть (дедуп)."""
        ...

    async def get(self, source: Source, external_id: str) -> Order | None: ...

    async def set_status(
        self,
        source: Source,
        external_id: str,
        status: OrderStatus,
        suitability_score: int | None,
    ) -> bool:
        """Меняет статус; `True`, если строка была обновлена."""
        ...


class OutboxRepository(Protocol):
    async def add_assessment_request(self, order: IncomingOrder) -> None:
        """Идемпотентно (по dedup_key) кладёт событие для очереди assess.requests."""
        ...

    async def add_notification(
        self, source: Source, external_id: str, notification: NotificationCommand
    ) -> None:
        """Идемпотентно (по dedup_key) кладёт событие для обменника notifications."""
        ...


class UnitOfWork(Protocol):
    orders: OrderRepository
    outbox: OutboxRepository

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, destination: str, payload: dict[str, Any]) -> None: ...


class OutboxDispatch(Protocol):
    """Транзакционный клейм outbox для реле (FOR UPDATE SKIP LOCKED)."""

    async def __aenter__(self) -> "OutboxDispatch": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...
    async def claim_pending(self, limit: int) -> list[PendingEvent]: ...
    async def mark_published(self, ids: list[uuid.UUID]) -> None: ...
    async def commit(self) -> None: ...


class Logger(Protocol):
    def debug(self, event: str, **fields: object) -> None: ...
    def info(self, event: str, **fields: object) -> None: ...
    def warning(self, event: str, **fields: object) -> None: ...
    def error(self, event: str, **fields: object) -> None: ...
