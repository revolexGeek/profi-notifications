"""Финальное решение: уведомлять или нет.

Детерминированная политика — жёсткие фильтры (unsupported/rejected) имеют
приоритет над баллом; по бюджету не отсекаем.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.assessment import Assessment

DecisionReason = Literal["above_threshold", "below_threshold", "unsupported_or_rejected"]


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    notify: bool
    reason: DecisionReason


def decide(assessment: Assessment, threshold: int) -> Decision:
    if assessment.unsupported_hits or assessment.is_rejected_type:
        return Decision(notify=False, reason="unsupported_or_rejected")
    if assessment.suitability_score >= threshold:
        return Decision(notify=True, reason="above_threshold")
    return Decision(notify=False, reason="below_threshold")
