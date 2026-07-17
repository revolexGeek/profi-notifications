"""Сценарий-реле outbox: публикация ожидающих событий в RabbitMQ (at-least-once).

Клеймит батч (FOR UPDATE SKIP LOCKED), публикует каждое событие, помечает
опубликованными и коммитит. Публикация at-least-once — потребители идемпотентны.
Публикация до commit: краш между ними → строка снова pending → повтор (дубль).
"""

from collections.abc import Callable

from app.application.ports import EventPublisher, Logger, OutboxDispatch


class RelayOutbox:
    def __init__(
        self,
        *,
        dispatch_factory: Callable[[], OutboxDispatch],
        publisher: EventPublisher,
        batch_size: int,
        logger: Logger,
    ) -> None:
        self._dispatch_factory = dispatch_factory
        self._publisher = publisher
        self._batch_size = batch_size
        self._logger = logger

    async def run_once(self) -> int:
        async with self._dispatch_factory() as dispatch:
            events = await dispatch.claim_pending(self._batch_size)
            if not events:
                return 0
            for event in events:
                await self._publisher.publish(event.destination, event.payload)
            await dispatch.mark_published([event.id for event in events])
            await dispatch.commit()
            self._logger.info("outbox_relayed", count=len(events))
            return len(events)
