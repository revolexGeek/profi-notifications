"""Маппинг wire↔domain и сборка исходящих payload'ов очередей."""

from typing import Any

from app.application.dto import IncomingOrder
from app.domain.assessment import AssessmentOutcome
from app.domain.notification import NotificationCommand
from app.domain.source import Source
from app.infrastructure.messaging.schemas import (
    AssessmentResultMessage,
    NotificationMessage,
    ParseResultMessage,
)


def to_incoming_orders(message: ParseResultMessage) -> list[IncomingOrder]:
    """Разбирает батч parse.results в приложенческие DTO (payload — сырой заказ)."""
    return [
        IncomingOrder(
            source=Source.PROFI,
            external_id=order.id,
            payload=order.model_dump(),
            request_id=message.request_id,
            fetched_at=message.fetched_at,
        )
        for order in message.orders
    ]


def to_assessment_outcome(message: AssessmentResultMessage) -> AssessmentOutcome:
    """Маппит вердикт assess.results в доменный AssessmentOutcome."""
    n = message.notification
    return AssessmentOutcome(
        order_id=message.order_id,
        suitability_score=message.suitability_score,
        notification=NotificationCommand(
            text=n.text,
            parse_mode=n.parse_mode,
            disable_notification=n.disable_notification,
            disable_web_page_preview=n.disable_web_page_preview,
            message_thread_id=n.message_thread_id,
        ),
    )


def assess_request_payload(order: IncomingOrder) -> dict[str, Any]:
    """Оборачивает один заказ в конверт ParseResultMessage для очереди assess.requests."""
    return {
        "request_id": order.request_id or "",
        "fetched_at": order.fetched_at,
        "total_count": 1,
        "next_cursor": None,
        "orders": [order.payload],
    }


def notification_payload(notification: NotificationCommand) -> dict[str, Any]:
    """camelCase-payload для обменника notifications (exclude_none — только заданное)."""
    return NotificationMessage(
        text=notification.text,
        parse_mode=notification.parse_mode,
        disable_notification=notification.disable_notification,
        disable_web_page_preview=notification.disable_web_page_preview,
        message_thread_id=notification.message_thread_id,
    ).model_dump(by_alias=True, exclude_none=True)
