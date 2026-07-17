"""Статусы жизненного цикла заявки и guard идемпотентности.

Разрешённые доменом переходы:
    (новая)          ──ingest──▶ ASSESS_REQUESTED
    ASSESS_REQUESTED ──notify──▶ NOTIFY_REQUESTED
    ASSESS_REQUESTED ──skip────▶ NO_NOTIFY

Повторная доставка вердикта в уже обработанную заявку — no-op (идемпотентность).
"""

from enum import StrEnum


class OrderStatus(StrEnum):
    ASSESS_REQUESTED = "assess_requested"
    NOTIFY_REQUESTED = "notify_requested"
    NO_NOTIFY = "no_notify"
    FAILED = "failed"


def can_apply_assessment(status: OrderStatus) -> bool:
    """Можно ли применить вердикт оценки — только к ещё не обработанной заявке."""
    return status is OrderStatus.ASSESS_REQUESTED
