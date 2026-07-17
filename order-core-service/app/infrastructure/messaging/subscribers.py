"""Подписчики parse.results и assess.results — Humble Objects.

Берут сырой dict (чтобы контролировать разбор и классификацию ошибок), парсят
wire-схему, маппят в domain/DTO и делегируют обработчику под `guard`. Бизнес-
логики здесь нет. NACK_ON_ERROR: временные сбои уходят на повтор, «ядовитое» и
постоянные — в DLQ силами `guard`.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from faststream import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.application.dto import IncomingOrder
from app.application.ports import Logger
from app.domain.assessment import AssessmentOutcome
from app.infrastructure.messaging.mapping import to_assessment_outcome, to_incoming_orders
from app.infrastructure.messaging.reliability import DeadLetterPublisher, guard
from app.infrastructure.messaging.schemas import AssessmentResultMessage, ParseResultMessage

IncomingOrdersHandler = Callable[[list[IncomingOrder]], Awaitable[None]]
AssessmentHandler = Callable[[AssessmentOutcome], Awaitable[None]]


def register_parse_subscriber(
    broker: RabbitBroker,
    queue: RabbitQueue,
    *,
    handle: IncomingOrdersHandler,
    dlq: DeadLetterPublisher,
    logger: Logger,
) -> None:
    async def _handle(message: ParseResultMessage) -> None:
        await handle(to_incoming_orders(message))

    @broker.subscriber(queue, ack_policy=AckPolicy.NACK_ON_ERROR)
    async def _on_parse_results(raw: dict[str, Any]) -> None:
        await guard(
            raw,
            ParseResultMessage.model_validate,
            _handle,
            dlq=dlq,
            logger=logger,
            queue=queue.name,
        )


def register_assess_subscriber(
    broker: RabbitBroker,
    queue: RabbitQueue,
    *,
    handle: AssessmentHandler,
    dlq: DeadLetterPublisher,
    logger: Logger,
) -> None:
    async def _handle(message: AssessmentResultMessage) -> None:
        await handle(to_assessment_outcome(message))

    @broker.subscriber(queue, ack_policy=AckPolicy.NACK_ON_ERROR)
    async def _on_assess_results(raw: dict[str, Any]) -> None:
        await guard(
            raw,
            AssessmentResultMessage.model_validate,
            _handle,
            dlq=dlq,
            logger=logger,
            queue=queue.name,
        )
