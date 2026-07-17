"""Входные DTO сценариев приложения.

`IncomingOrder` — принятая заявка: идентичность для дедупа + сырой заказ, который
«мозг» форвардит в llm как есть (домен его не интерпретирует).
"""

from typing import Any

from pydantic import BaseModel

from app.domain.source import Source

OrderPayload = dict[str, Any]


class IncomingOrder(BaseModel):
    source: Source
    external_id: str
    payload: OrderPayload
    request_id: str | None = None
    fetched_at: int = 0
