"""Вердикт оценки заявки — вход «мозга» от llm (`assess.results`).

llm отдаёт готовое уведомление вместе с баллом соответствия; решение о финальной
отправке принимает «мозг».
"""

from pydantic import BaseModel, ConfigDict, Field

from app.domain.notification import NotificationCommand


class AssessmentOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    suitability_score: int = Field(ge=0, le=100)
    notification: NotificationCommand
