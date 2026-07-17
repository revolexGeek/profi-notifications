"""Контракт-тесты исходящих сообщений: наши payload'ы должны подходить соседям.

`assess.requests` проверяем разбором через ту же `ParseResultMessage` (её читает
llm). `notify` — зеркалом zod-схемы notifications (message-schema.ts).
"""

from typing import Any

from app.application.dto import IncomingOrder
from app.domain.notification import NotificationCommand
from app.domain.source import Source
from app.infrastructure.messaging.mapping import assess_request_payload, notification_payload
from app.infrastructure.messaging.schemas import ParseResultMessage

_PARSE_MODES = {"HTML", "MarkdownV2", "Markdown"}
_ALLOWED_NOTIFY_KEYS = {
    "text",
    "parseMode",
    "disableNotification",
    "disableWebPagePreview",
    "messageThreadId",
}


def _assert_notifications_contract(payload: dict[str, Any]) -> None:
    """Зеркало notifications/src/infrastructure/messaging/message-schema.ts (zod)."""
    assert isinstance(payload["text"], str) and payload["text"]
    assert set(payload).issubset(_ALLOWED_NOTIFY_KEYS)  # неизвестные ключи не шлём
    if "parseMode" in payload:
        assert payload["parseMode"] in _PARSE_MODES
    if "messageThreadId" in payload:
        assert isinstance(payload["messageThreadId"], int) and payload["messageThreadId"] > 0


def test_assess_request_is_parseable_by_llm_schema() -> None:
    order = IncomingOrder(
        source=Source.PROFI,
        external_id="42",
        payload={"id": "42", "title": "t", "description": "d"},
        request_id="req-9",
        fetched_at=123,
    )

    payload = assess_request_payload(order)

    parsed = ParseResultMessage.model_validate(payload)
    assert parsed.total_count == 1
    assert len(parsed.orders) == 1
    assert parsed.orders[0].id == "42"
    assert parsed.request_id == "req-9"


def test_notify_payload_is_camel_case_and_matches_contract() -> None:
    command = NotificationCommand(text="привет", parse_mode="HTML", disable_web_page_preview=True)

    payload = notification_payload(command)

    assert payload == {"text": "привет", "parseMode": "HTML", "disableWebPagePreview": True}
    _assert_notifications_contract(payload)


def test_notify_payload_omits_unset_fields() -> None:
    payload = notification_payload(NotificationCommand(text="t"))

    assert payload == {"text": "t"}  # exclude_none → шлём только заданные поля
