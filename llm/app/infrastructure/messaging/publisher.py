"""Публикация результата оценки в очередь assess.results (реализация ResultPublisher)."""

from typing import Any, Protocol

from app.domain.result import AssessmentResult
from app.infrastructure.messaging.schemas import AssessmentResultMessage


class PublisherTransport(Protocol):
    """Минимальный контракт FastStream-паблишера, который нужен адаптеру."""

    async def publish(self, message: Any) -> Any: ...


class RabbitResultPublisher:
    def __init__(self, publisher: PublisherTransport) -> None:
        self._publisher = publisher

    async def publish(self, result: AssessmentResult) -> None:
        message = AssessmentResultMessage.from_result(result)
        await self._publisher.publish(message.model_dump(by_alias=True, exclude_none=True))
