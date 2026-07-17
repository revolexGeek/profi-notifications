"""Классификация сбоев приёма: poison/permanent → DLQ, transient → повтор.

Подписчик берёт сырой dict и прогоняет его через `guard`:
- ошибка разбора (невалидный payload) или `PermanentError` → публикуем в DLQ и ack;
- прочие ошибки (БД/сеть) → пробрасываем → NACK/requeue (повтор).

DLQ — на уровне приложения (publish в `order.dlq`), т.к. очередь `assess.results`
объявляет llm без dead-letter-аргументов, и брокерный DLX на неё навесить нельзя.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError

from app.application.errors import PermanentError
from app.application.ports import Logger
from app.infrastructure.messaging.publisher import PublisherTransport


class DeadLetterPublisher:
    def __init__(self, publisher: PublisherTransport) -> None:
        self._publisher = publisher

    async def publish(self, payload: Any, *, category: str, reason: str) -> None:
        await self._publisher.publish(
            {"category": category, "reason": reason, "payload": payload}
        )


async def guard(
    raw: dict[str, Any],
    parse: Callable[[dict[str, Any]], Any],
    handle: Callable[[Any], Awaitable[None]],
    *,
    dlq: DeadLetterPublisher,
    logger: Logger,
    queue: str,
) -> None:
    try:
        message = parse(raw)
    except ValidationError as exc:
        await dlq.publish(raw, category="invalid-payload", reason=str(exc))
        logger.warning("message_dead_lettered", queue=queue, category="invalid-payload")
        return
    try:
        await handle(message)
    except PermanentError as exc:
        await dlq.publish(raw, category="permanent", reason=str(exc))
        logger.warning(
            "message_dead_lettered", queue=queue, category="permanent", error=str(exc)
        )
        return
    # Прочее (transient: БД/сеть) не глушим — пробрасываем на NACK/requeue → повтор.
