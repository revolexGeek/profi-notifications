"""Тесты политики «слать/не слать» уведомление.

llm присылает только подходящие вердикты; порог «мозга» — дополнительный фильтр
поверх (по умолчанию 0 = доверяем llm).
"""

from app.domain.assessment import AssessmentOutcome
from app.domain.decision import decide_notification
from app.domain.notification import NotificationCommand


def _outcome(score: int) -> AssessmentOutcome:
    return AssessmentOutcome(
        order_id="1", suitability_score=score, notification=NotificationCommand(text="t")
    )


def test_notifies_at_or_above_threshold() -> None:
    decision = decide_notification(_outcome(60), threshold=60)

    assert decision.notify is True
    assert decision.reason == "above_threshold"


def test_skips_below_threshold() -> None:
    decision = decide_notification(_outcome(59), threshold=60)

    assert decision.notify is False
    assert decision.reason == "below_threshold"


def test_zero_threshold_trusts_llm() -> None:
    decision = decide_notification(_outcome(0), threshold=0)

    assert decision.notify is True
