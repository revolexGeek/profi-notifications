"""Доменная сущность заявки. Идентичность = (`source`, `external_id`).

Узкая проекция для решений «мозга»: домену нужны только идентичность, статус и
балл. Сырой заказ (для форварда в llm) хранит инфраструктура — в домен не течёт.
"""

from pydantic import BaseModel, ConfigDict

from app.domain.source import Source
from app.domain.status import OrderStatus


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Source
    external_id: str
    status: OrderStatus
    suitability_score: int | None = None
