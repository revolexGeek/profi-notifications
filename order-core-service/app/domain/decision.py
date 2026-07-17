"""Политика «слать/не слать» уведомление — детерминированная и чистая.

llm присылает только подходящие вердикты; порог «мозга» — дополнительный фильтр
поверх (0 = доверяем llm).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.assessment import AssessmentOutcome

DecisionReason = Literal["above_threshold", "below_threshold"]


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    notify: bool
    reason: DecisionReason


def decide_notification(outcome: AssessmentOutcome, threshold: int) -> Decision:
    if outcome.suitability_score >= threshold:
        return Decision(notify=True, reason="above_threshold")
    return Decision(notify=False, reason="below_threshold")
