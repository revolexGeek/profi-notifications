"""Тесты wire-моделей: camelCase-уведомление и результат оценки для «мозга»."""

from app.domain.notification import NotificationCommand
from app.domain.result import AssessmentResult
from app.infrastructure.messaging.schemas import AssessmentResultMessage, NotificationMessage


def test_serializes_to_camel_case_without_none() -> None:
    command = NotificationCommand(text="привет", parse_mode="HTML")

    payload = NotificationMessage.from_command(command).model_dump(by_alias=True, exclude_none=True)

    assert payload == {"text": "привет", "parseMode": "HTML", "disableWebPagePreview": True}
    assert "disableNotification" not in payload
    assert "messageThreadId" not in payload


def test_result_message_wraps_camel_case_notification() -> None:
    result = AssessmentResult(
        order_id="7",
        suitability_score=91,
        notification=NotificationCommand(text="hi", parse_mode="HTML"),
    )

    payload = AssessmentResultMessage.from_result(result).model_dump(
        by_alias=True, exclude_none=True
    )

    assert payload == {
        "order_id": "7",
        "suitability_score": 91,
        "notification": {"text": "hi", "parseMode": "HTML", "disableWebPagePreview": True},
    }
