"""Формирование текста уведомления для Telegram (HTML).

Домен отдаёт нейтральную команду; инфраструктура маппит её в wire-модель
очереди `notifications`. Лимит длины считаем в UTF-16 code units — так же,
как его проверяет сервис-получатель (Telegram Bot API).
"""

import html
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.assessment import Assessment
from app.domain.listing import Listing

MAX_TEXT_LENGTH = 4096
_ELLIPSIS = "…"
_SEPARATOR = "\n\n"

ParseMode = Literal["HTML", "MarkdownV2", "Markdown"]


class NotificationCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    parse_mode: ParseMode = "HTML"
    disable_web_page_preview: bool = True


def _tg_len(text: str) -> int:
    """Длина в UTF-16 code units (астральные emoji считаются за 2)."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in text)


def _truncate(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if _tg_len(text) <= limit:
        return text
    budget = limit - _tg_len(_ELLIPSIS)
    kept: list[str] = []
    used = 0
    for ch in text:
        width = 2 if ord(ch) > 0xFFFF else 1
        if used + width > budget:
            break
        kept.append(ch)
        used += width
    return "".join(kept).rstrip() + _ELLIPSIS


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def build_notification(listing: Listing, assessment: Assessment) -> NotificationCommand:
    title = _escape(listing.title.strip() or "Без названия")
    header = f'🧩 <b><a href="{listing.url}">{title}</a></b>'

    meta_lines: list[str] = []
    if listing.budget is not None:
        meta_lines.append(f"💰 {_escape(listing.budget.raw)}")
    meta_lines.append(f"🎯 Соответствие: {assessment.suitability_score}/100")
    meta = "\n".join(meta_lines)

    summary = _escape(assessment.summary.strip())
    overhead = _tg_len(header) + _tg_len(meta) + _tg_len(_SEPARATOR) * 2
    summary = _truncate(summary, MAX_TEXT_LENGTH - overhead)

    parts = [header, summary, meta] if summary else [header, meta]
    text = _SEPARATOR.join(parts)
    return NotificationCommand(text=_truncate(text, MAX_TEXT_LENGTH))
