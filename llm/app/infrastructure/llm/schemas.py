"""Схема структурированного вывода LLM.

Отдаётся модели через with_structured_output (function calling). Описания
полей попадают в схему инструмента и направляют модель. В домен маппится в
Assessment — эта схема наружу слоя не течёт.
"""

from pydantic import BaseModel, Field


class LlmAssessmentSchema(BaseModel):
    summary: str = Field(description="Краткая суть заказа, 1-2 предложения на русском.")
    detected_skills: list[str] = Field(
        default_factory=list, description="Навыки/технологии, которые реально требует заказ."
    )
    matched_strong: list[str] = Field(
        default_factory=list, description="Из detected_skills — совпавшие с сильными навыками."
    )
    matched_working: list[str] = Field(
        default_factory=list, description="Из detected_skills — совпавшие с рабочими навыками."
    )
    unsupported_hits: list[str] = Field(
        default_factory=list,
        description="Из detected_skills — попавшие в неподдерживаемые навыки исполнителя.",
    )
    is_rejected_type: bool = Field(
        default=False,
        description=(
            "Заказ из нежелательных типов: учебные работы, чистый фронтенд, дизайн, накрутка."
        ),
    )
    suitability_score: int = Field(
        ge=0, le=100, description="Насколько заказ подходит исполнителю, 0-100."
    )
    rationale: str = Field(default="", description="Короткое обоснование оценки.")
