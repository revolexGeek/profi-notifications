"""Публикация уведомления в очередь notifications (реализация NotificationPublisher)."""

from typing import Any, Protocol

from app.domain.notification import NotificationCommand
from app.infrastructure.messaging.schemas import NotificationMessage


class PublisherTransport(Protocol):
    """Минимальный контракт FastStream-паблишера, который нужен адаптеру."""

    async def publish(self, message: Any) -> Any: ...


class RabbitNotificationPublisher:
    def __init__(self, publisher: PublisherTransport) -> None:
        self._publisher = publisher

    async def publish(self, command: NotificationCommand) -> None:
        message = NotificationMessage.from_command(command)
        await self._publisher.publish(message.model_dump(by_alias=True, exclude_none=True))
