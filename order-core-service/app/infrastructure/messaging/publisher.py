"""Транспорт публикации FastStream — минимальный контракт для адаптеров/реле."""

from typing import Any, Protocol


class PublisherTransport(Protocol):
    """Минимальный контракт FastStream-паблишера, который нужен реле outbox."""

    async def publish(self, message: Any) -> Any: ...
