"""Тесты доменного вердикта оценки (вход от llm)."""

import pytest
from pydantic import ValidationError

from app.domain.assessment import AssessmentOutcome
from app.domain.notification import NotificationCommand


def test_holds_verdict_with_ready_notification() -> None:
    outcome = AssessmentOutcome(
        order_id="91668753",
        suitability_score=90,
        notification=NotificationCommand(text="готовое уведомление"),
    )

    assert outcome.order_id == "91668753"
    assert outcome.suitability_score == 90
    assert outcome.notification.text == "готовое уведомление"


@pytest.mark.parametrize("score", [-1, 101])
def test_rejects_score_out_of_bounds(score: int) -> None:
    with pytest.raises(ValidationError):
        AssessmentOutcome(
            order_id="1",
            suitability_score=score,
            notification=NotificationCommand(text="t"),
        )
