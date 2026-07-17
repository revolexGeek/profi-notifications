"""Тесты доменной команды уведомления (нейтральный форвард-контракт)."""

import pytest
from pydantic import ValidationError

from app.domain.notification import NotificationCommand


def test_only_text_is_required() -> None:
    command = NotificationCommand(text="привет")

    assert command.text == "привет"
    # Остальное форвардим как есть — по умолчанию не задано (None).
    assert command.parse_mode is None
    assert command.disable_notification is None
    assert command.disable_web_page_preview is None
    assert command.message_thread_id is None


def test_keeps_all_fields() -> None:
    command = NotificationCommand(
        text="t",
        parse_mode="HTML",
        disable_notification=False,
        disable_web_page_preview=True,
        message_thread_id=2,
    )

    assert command.parse_mode == "HTML"
    assert command.message_thread_id == 2


def test_is_frozen() -> None:
    command = NotificationCommand(text="t")

    with pytest.raises(ValidationError):
        command.text = "changed"  # type: ignore[misc]
