"""Тесты wire-модели уведомления (camelCase-контракт очереди notifications)."""

from app.domain.notification import NotificationCommand
from app.infrastructure.messaging.schemas import NotificationMessage


def test_serializes_to_camel_case_without_none() -> None:
    command = NotificationCommand(text="привет", parse_mode="HTML")

    payload = NotificationMessage.from_command(command).model_dump(by_alias=True, exclude_none=True)

    assert payload == {"text": "привет", "parseMode": "HTML", "disableWebPagePreview": True}
    assert "disableNotification" not in payload
    assert "messageThreadId" not in payload
