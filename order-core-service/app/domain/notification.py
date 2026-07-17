"""Доменная команда уведомления — нейтральный форвард-контракт.

«Мозг» получает от llm готовое уведомление и пробрасывает его в сервис
notifications как есть. Поля повторяют контракт notifications (всё, кроме `text`,
опционально); домен их не интерпретирует.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

ParseMode = Literal["HTML", "MarkdownV2", "Markdown"]


class NotificationCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    parse_mode: ParseMode | None = None
    disable_notification: bool | None = None
    disable_web_page_preview: bool | None = None
    message_thread_id: int | None = None
