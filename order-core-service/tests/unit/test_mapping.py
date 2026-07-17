"""Тесты маппинга wire↔domain."""

from app.domain.source import Source
from app.infrastructure.messaging.mapping import to_assessment_outcome, to_incoming_orders
from app.infrastructure.messaging.schemas import (
    AssessmentResultMessage,
    NotificationMessage,
    Order,
    ParseResultMessage,
)


def test_to_incoming_orders_extracts_identity_and_payload() -> None:
    message = ParseResultMessage(
        request_id="r1",
        fetched_at=99,
        orders=[Order(id="7", title="A"), Order(id="8", title="B")],
    )

    incoming = to_incoming_orders(message)

    assert [o.external_id for o in incoming] == ["7", "8"]
    assert all(o.source is Source.PROFI for o in incoming)
    assert incoming[0].request_id == "r1"
    assert incoming[0].fetched_at == 99
    assert incoming[0].payload["id"] == "7"  # сырой заказ для форварда в llm


def test_to_assessment_outcome_maps_notification_to_domain() -> None:
    message = AssessmentResultMessage(
        order_id="7",
        suitability_score=88,
        notification=NotificationMessage(
            text="t", parse_mode="HTML", disable_web_page_preview=True
        ),
    )

    outcome = to_assessment_outcome(message)

    assert outcome.order_id == "7"
    assert outcome.suitability_score == 88
    assert outcome.notification.text == "t"
    assert outcome.notification.parse_mode == "HTML"
    assert outcome.notification.disable_web_page_preview is True
