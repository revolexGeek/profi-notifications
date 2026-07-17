"""Интеграционные тесты messaging через in-memory TestRabbitBroker (без брокера)."""

from typing import Any, cast

from faststream.rabbit import RabbitBroker, TestRabbitBroker

from app.application.dto import IncomingOrder
from app.domain.assessment import AssessmentOutcome
from app.domain.source import Source
from app.infrastructure.messaging.broker import (
    build_assess_request_publisher,
    build_assess_result_queue,
    build_notify_publisher,
    build_parse_queue,
)
from app.infrastructure.messaging.subscribers import (
    register_assess_subscriber,
    register_parse_subscriber,
)

_PARSE_RESULT = {
    "request_id": "r1",
    "fetched_at": 1,
    "total_count": 2,
    "next_cursor": None,
    "orders": [{"id": "1", "title": "A"}, {"id": "2", "title": "B"}],
}

_ASSESS_RESULT = {
    "order_id": "7",
    "suitability_score": 88,
    "notification": {"text": "t", "parseMode": "HTML", "disableWebPagePreview": True},
}


async def test_parse_subscriber_maps_and_delegates() -> None:
    seen: list[IncomingOrder] = []

    async def handle(orders: list[IncomingOrder]) -> None:
        seen.extend(orders)

    broker = RabbitBroker()
    register_parse_subscriber(broker, build_parse_queue("parse.results", dlx="order.dlx"), handle)

    async with TestRabbitBroker(broker) as br:
        await br.publish(_PARSE_RESULT, queue="parse.results")

    assert [o.external_id for o in seen] == ["1", "2"]
    assert seen[0].source is Source.PROFI
    assert seen[0].payload["id"] == "1"


async def test_assess_subscriber_maps_and_delegates() -> None:
    seen: list[AssessmentOutcome] = []

    async def handle(outcome: AssessmentOutcome) -> None:
        seen.append(outcome)

    broker = RabbitBroker()
    register_assess_subscriber(broker, build_assess_result_queue("assess.results"), handle)

    async with TestRabbitBroker(broker) as br:
        await br.publish(_ASSESS_RESULT, queue="assess.results")

    assert seen[0].order_id == "7"
    assert seen[0].suitability_score == 88
    assert seen[0].notification.parse_mode == "HTML"
    assert seen[0].notification.disable_web_page_preview is True


async def test_assess_request_publisher_targets_queue() -> None:
    broker = RabbitBroker()
    publisher = build_assess_request_publisher(broker, queue="assess.requests")

    async with TestRabbitBroker(broker):
        await publisher.publish({"request_id": "r", "orders": []})
        cast(Any, publisher).mock.assert_called_once_with({"request_id": "r", "orders": []})


async def test_notify_publisher_targets_exchange() -> None:
    broker = RabbitBroker()
    publisher = build_notify_publisher(broker, exchange="notifications", routing_key="notify")

    async with TestRabbitBroker(broker):
        await publisher.publish({"text": "hi"})
        cast(Any, publisher).mock.assert_called_once_with({"text": "hi"})
