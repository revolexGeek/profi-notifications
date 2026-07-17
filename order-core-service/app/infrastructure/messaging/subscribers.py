"""Подписчики parse.results и assess.results — Humble Objects.

Только десериализация (Pydantic), маппинг в domain/DTO и делегирование
обработчику. Бизнес-логики здесь нет. REJECT_ON_ERROR: нераспарсиваемый конверт
уходит в DLQ, а не крутится в hot-loop.
"""

from collections.abc import Awaitable, Callable

from faststream import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.application.dto import IncomingOrder
from app.domain.assessment import AssessmentOutcome
from app.infrastructure.messaging.mapping import to_assessment_outcome, to_incoming_orders
from app.infrastructure.messaging.schemas import AssessmentResultMessage, ParseResultMessage

IncomingOrdersHandler = Callable[[list[IncomingOrder]], Awaitable[None]]
AssessmentHandler = Callable[[AssessmentOutcome], Awaitable[None]]


def register_parse_subscriber(
    broker: RabbitBroker, queue: RabbitQueue, handle: IncomingOrdersHandler
) -> None:
    @broker.subscriber(queue, ack_policy=AckPolicy.REJECT_ON_ERROR)
    async def _on_parse_results(message: ParseResultMessage) -> None:
        await handle(to_incoming_orders(message))


def register_assess_subscriber(
    broker: RabbitBroker, queue: RabbitQueue, handle: AssessmentHandler
) -> None:
    @broker.subscriber(queue, ack_policy=AckPolicy.REJECT_ON_ERROR)
    async def _on_assess_results(message: AssessmentResultMessage) -> None:
        await handle(to_assessment_outcome(message))
