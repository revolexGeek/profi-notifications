"""Сценарий обработки вердикта оценки: решение об уведомлении + outbox(notify).

Идемпотентность — через guard `can_apply_assessment` (повторный вердикт по уже
обработанной заявке = no-op) и dedup_key события notify. Неизвестная заявка —
`PermanentError` (в DLQ): outbox гарантирует «сначала persist, потом publish»,
поэтому llm не может ответить по заявке, которой у нас нет.
"""

from collections.abc import Callable

from app.application.errors import PermanentError
from app.application.ports import Logger, UnitOfWork
from app.domain.assessment import AssessmentOutcome
from app.domain.decision import decide_notification
from app.domain.source import Source
from app.domain.status import OrderStatus, can_apply_assessment


class ProcessAssessment:
    def __init__(
        self, *, uow_factory: Callable[[], UnitOfWork], threshold: int, logger: Logger
    ) -> None:
        self._uow_factory = uow_factory
        self._threshold = threshold
        self._logger = logger

    async def handle(self, outcome: AssessmentOutcome) -> None:
        async with self._uow_factory() as uow:
            order = await uow.orders.get(Source.PROFI, outcome.order_id)
            if order is None:
                raise PermanentError(f"unknown order {outcome.order_id}")

            if not can_apply_assessment(order.status):
                self._logger.info(
                    "assessment_ignored",
                    external_id=outcome.order_id,
                    status=str(order.status),
                )
                await uow.commit()
                return

            decision = decide_notification(outcome, self._threshold)
            if decision.notify:
                await uow.orders.set_status(
                    Source.PROFI,
                    outcome.order_id,
                    OrderStatus.NOTIFY_REQUESTED,
                    outcome.suitability_score,
                )
                await uow.outbox.add_notification(
                    Source.PROFI, outcome.order_id, outcome.notification
                )
                self._logger.info(
                    "notification_requested",
                    external_id=outcome.order_id,
                    score=outcome.suitability_score,
                )
            else:
                await uow.orders.set_status(
                    Source.PROFI,
                    outcome.order_id,
                    OrderStatus.NO_NOTIFY,
                    outcome.suitability_score,
                )
                self._logger.info(
                    "order_no_notify",
                    external_id=outcome.order_id,
                    reason=decision.reason,
                )
            await uow.commit()
