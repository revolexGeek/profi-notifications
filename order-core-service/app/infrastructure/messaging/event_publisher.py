"""Публикация outbox-события в нужный транспорт FastStream по его назначению."""

from typing import Any

from app.infrastructure.db.models import OutboxDestination
from app.infrastructure.messaging.publisher import PublisherTransport


class FastStreamEventPublisher:
    def __init__(self, *, assess_request: PublisherTransport, notify: PublisherTransport) -> None:
        self._by_destination: dict[str, PublisherTransport] = {
            OutboxDestination.ASSESS_REQUEST.value: assess_request,
            OutboxDestination.NOTIFY.value: notify,
        }

    async def publish(self, destination: str, payload: dict[str, Any]) -> None:
        publisher = self._by_destination.get(destination)
        if publisher is None:
            raise ValueError(f"неизвестное назначение outbox: {destination}")
        await publisher.publish(payload)
