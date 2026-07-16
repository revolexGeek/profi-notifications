"""Доменная заявка Profi.ru и разбор бюджета.

`Listing` — узкая доменная проекция заказа (маппинг из wire-модели делает
инфраструктура). Бюджет разбираем best-effort только для показа — по нему
не отсекаем.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Bound = Literal["up_to", "from"]

_BOUND_BY_PREFIX: dict[str, Bound] = {"до": "up_to", "от": "from"}
# Первое число с внутренними пробелами-разделителями тысяч
# (\s в Unicode-режиме покрывает обычный, неразрывный и тонкий пробелы).
_AMOUNT_RE = re.compile(r"\d[\d\s]*")


class Budget(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw: str
    amount: int | None = None
    currency: str | None = None
    bound: Bound | None = None

    @classmethod
    def from_price(cls, prefix: str, value: str, suffix: str) -> "Budget | None":
        """Собирает бюджет из частей Profi (`prefix`/`value`/`suffix`).

        Возвращает None, если показывать нечего.
        """
        raw = " ".join(part for part in (prefix, value, suffix) if part).strip()
        if not raw:
            return None
        match = _AMOUNT_RE.search(value)
        amount = int(re.sub(r"\D", "", match.group())) if match else None
        currency = "₽" if "₽" in f"{value}{suffix}" else None
        bound = _BOUND_BY_PREFIX.get(prefix.strip().lower())
        return cls(raw=raw, amount=amount, currency=currency, bound=bound)


class Listing(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    budget: Budget | None = None
    is_remote: bool = False
    location: str | None = None
    client_tags: list[str] = Field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://profi.ru/backoffice/n.php?o={self.id}"
