"""Фейковые реализации портов приложения для тестов (без БД и брокера)."""

import uuid
from types import TracebackType

from app.application.dto import IncomingOrder, PendingEvent
from app.domain.notification import NotificationCommand
from app.domain.order import Order
from app.domain.source import Source
from app.domain.status import OrderStatus


class FakeOrderRepository:
    def __init__(self, store: dict[tuple[Source, str], Order]) -> None:
        self._store = store

    async def insert_new(self, order: IncomingOrder) -> bool:
        key = (order.source, order.external_id)
        if key in self._store:
            return False
        self._store[key] = Order(
            source=order.source,
            external_id=order.external_id,
            status=OrderStatus.ASSESS_REQUESTED,
        )
        return True

    async def get(self, source: Source, external_id: str) -> Order | None:
        return self._store.get((source, external_id))

    async def set_status(
        self,
        source: Source,
        external_id: str,
        status: OrderStatus,
        suitability_score: int | None,
    ) -> bool:
        key = (source, external_id)
        current = self._store.get(key)
        if current is None:
            return False
        self._store[key] = current.model_copy(
            update={"status": status, "suitability_score": suitability_score}
        )
        return True


class FakeOutbox:
    def __init__(self) -> None:
        self.assess: list[IncomingOrder] = []
        self.notify: list[tuple[Source, str, NotificationCommand]] = []
        self._dedup: set[str] = set()

    async def add_assessment_request(self, order: IncomingOrder) -> None:
        key = f"assess:{order.source}:{order.external_id}"
        if key in self._dedup:
            return
        self._dedup.add(key)
        self.assess.append(order)

    async def add_notification(
        self, source: Source, external_id: str, notification: NotificationCommand
    ) -> None:
        key = f"notify:{source}:{external_id}"
        if key in self._dedup:
            return
        self._dedup.add(key)
        self.notify.append((source, external_id, notification))


class FakeUnitOfWork:
    def __init__(self, factory: "FakeUnitOfWorkFactory") -> None:
        self._factory = factory
        self.orders = FakeOrderRepository(factory.order_store)
        self.outbox = factory.outbox

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        if exc_type is not None:
            self._factory.rolled_back_count += 1
        return False

    async def commit(self) -> None:
        self._factory.committed_count += 1

    async def rollback(self) -> None:
        self._factory.rolled_back_count += 1


class FakeUnitOfWorkFactory:
    def __init__(self) -> None:
        self.order_store: dict[tuple[Source, str], Order] = {}
        self.outbox = FakeOutbox()
        self.committed_count = 0
        self.rolled_back_count = 0

    def __call__(self) -> FakeUnitOfWork:
        return FakeUnitOfWork(self)


class FakeLogger:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, object]]] = []

    def _record(self, level: str, event: str, **fields: object) -> None:
        self.events.append((level, event, fields))

    def debug(self, event: str, **fields: object) -> None:
        self._record("debug", event, **fields)

    def info(self, event: str, **fields: object) -> None:
        self._record("info", event, **fields)

    def warning(self, event: str, **fields: object) -> None:
        self._record("warning", event, **fields)

    def error(self, event: str, **fields: object) -> None:
        self._record("error", event, **fields)

    def events_of(self, event: str) -> list[dict[str, object]]:
        return [fields for _, name, fields in self.events if name == event]


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, object]]] = []

    async def publish(self, destination: str, payload: dict[str, object]) -> None:
        self.published.append((destination, payload))


class FakeOutboxDispatch:
    def __init__(self, factory: "FakeOutboxDispatchFactory") -> None:
        self._factory = factory

    async def __aenter__(self) -> "FakeOutboxDispatch":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        return False

    async def claim_pending(self, limit: int) -> list[PendingEvent]:
        return self._factory.pending[:limit]

    async def mark_published(self, ids: list[uuid.UUID]) -> None:
        marked = set(ids)
        self._factory.published_ids.extend(ids)
        self._factory.pending = [e for e in self._factory.pending if e.id not in marked]

    async def commit(self) -> None:
        self._factory.committed_count += 1


class FakeOutboxDispatchFactory:
    def __init__(self, pending: list[PendingEvent]) -> None:
        self.pending = list(pending)
        self.published_ids: list[uuid.UUID] = []
        self.committed_count = 0

    def __call__(self) -> FakeOutboxDispatch:
        return FakeOutboxDispatch(self)
