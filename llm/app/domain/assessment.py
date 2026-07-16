"""Вердикт оценки заявки в доменных терминах.

Инфраструктурный LLM-адаптер маппит структурированный вывод модели в этот
объект — wire-схема LLM в домен не течёт.
"""

from pydantic import BaseModel, ConfigDict, Field


class Assessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: str
    suitability_score: int = Field(ge=0, le=100)
    unsupported_hits: list[str] = Field(default_factory=list)
    is_rejected_type: bool = False
    matched_strong: list[str] = Field(default_factory=list)
    matched_working: list[str] = Field(default_factory=list)
    rationale: str = ""
