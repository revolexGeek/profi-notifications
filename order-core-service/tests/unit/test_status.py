"""Тесты статусов заявки и guard'а идемпотентности."""

import pytest

from app.domain.status import OrderStatus, can_apply_assessment


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OrderStatus.ASSESS_REQUESTED, True),
        (OrderStatus.NOTIFY_REQUESTED, False),
        (OrderStatus.NO_NOTIFY, False),
        (OrderStatus.FAILED, False),
    ],
)
def test_can_apply_assessment_only_from_assess_requested(
    status: OrderStatus, expected: bool
) -> None:
    # Вердикт применяется лишь один раз — повторная доставка assess.results = no-op.
    assert can_apply_assessment(status) is expected
