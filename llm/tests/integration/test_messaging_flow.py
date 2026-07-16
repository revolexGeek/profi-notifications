"""Интеграционные тесты messaging через in-memory TestRabbitBroker."""

from faststream.rabbit import RabbitBroker, TestRabbitBroker

from app.domain.listing import Listing
from app.domain.notification import NotificationCommand
from app.infrastructure.messaging.broker import (
    build_input_queue,
    build_notification_publisher,
)
from app.infrastructure.messaging.publisher import RabbitNotificationPublisher
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
    register_orders_subscriber(broker, build_input_queue("parse.results"), handle)

    async with TestRabbitBroker(broker) as br:
        await br.publish(_PARSE_RESULT, queue="parse.results")

    assert [listing.id for listing in seen] == ["1", "2"]
    assert seen[0].is_remote is True
    assert seen[0].budget is not None


async def test_publisher_sends_camel_case_to_notifications() -> None:
    broker = RabbitBroker()
    notify_publisher = build_notification_publisher(broker)
    adapter = RabbitNotificationPublisher(notify_publisher)

    async with TestRabbitBroker(broker):
        await adapter.publish(NotificationCommand(text="hi", parse_mode="HTML"))
        notify_publisher.mock.assert_called_once_with(
            {"text": "hi", "parseMode": "HTML", "disableWebPagePreview": True}
        )
