"""Интеграционные тесты messaging через in-memory TestRabbitBroker."""

from typing import Any, cast

from faststream.rabbit import RabbitBroker, TestRabbitBroker

from app.domain.listing import Listing
from app.domain.notification import NotificationCommand
from app.domain.result import AssessmentResult
from app.infrastructure.messaging.broker import build_input_queue, build_result_publisher
from app.infrastructure.messaging.publisher import RabbitResultPublisher
from app.infrastructure.messaging.subscriber import register_orders_subscriber

_PARSE_RESULT = {
    "request_id": "r1",
    "fetched_at": 1,
    "total_count": 2,
    "next_cursor": None,
    "orders": [
        {
            "id": "1",
            "title": "A",
            "description": "d",
            "price": {"prefix": "до", "value": "700 ₽", "suffix": ""},
            "geo": {
                "remote": {"prefix": "Дистанционно", "suffix": "", "address": None},
                "order_location": None,
                "client_may_come": None,
            },
            "client": {"name": "n", "tags": ["новый"]},
            "badges": [],
            "schedule": None,
            "last_update": 0,
            "score": 80.5,
            "is_fresh": False,
            "is_viewed": False,
            "coordinates": None,
        },
        {
            "id": "2",
            "title": "B",
            "description": "d",
            "price": None,
            "geo": {"remote": None, "order_location": None, "client_may_come": None},
            "client": {"name": "n", "tags": []},
            "badges": [],
            "schedule": None,
            "last_update": 0,
            "score": 1.0,
            "is_fresh": False,
            "is_viewed": False,
            "coordinates": None,
        },
    ],
}


async def test_subscriber_maps_orders_and_delegates() -> None:
    seen: list[Listing] = []

    async def handle(listings: list[Listing]) -> None:
        seen.extend(listings)

    broker = RabbitBroker()
    register_orders_subscriber(broker, build_input_queue("assess.requests"), handle)

    async with TestRabbitBroker(broker) as br:
        await br.publish(_PARSE_RESULT, queue="assess.requests")

    assert [listing.id for listing in seen] == ["1", "2"]
    assert seen[0].is_remote is True
    assert seen[0].budget is not None


async def test_publisher_sends_result_to_assess_results() -> None:
    broker = RabbitBroker()
    result_publisher = build_result_publisher(broker, queue="assess.results")
    adapter = RabbitResultPublisher(result_publisher)
    result = AssessmentResult(
        order_id="42",
        suitability_score=88,
        notification=NotificationCommand(text="hi", parse_mode="HTML"),
    )

    async with TestRabbitBroker(broker):
        await adapter.publish(result)
        # .mock навешивает TestRabbitBroker в рантайме; у типа PublisherTransport его нет
        cast(Any, result_publisher).mock.assert_called_once_with(
            {
                "order_id": "42",
                "suitability_score": 88,
                "notification": {
                    "text": "hi",
                    "parseMode": "HTML",
                    "disableWebPagePreview": True,
                },
            }
        )
