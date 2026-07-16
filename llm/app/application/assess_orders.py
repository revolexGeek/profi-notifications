"""Сценарий оценки заказов.

На входе — уже смапленные доменные `Listing` (десериализацию и маппинг из
wire-модели делает подписчик). Обработка best-effort: сбой одного заказа
логируется и не рушит остальные — потерянный заказ вернётся с ре-поллом.
"""

from app.application.errors import AssessmentError
from app.application.ports import LlmAssessor, Logger, NotificationPublisher
from app.domain.decision import decide
from app.domain.listing import Listing
from app.domain.notification import build_notification
from app.domain.profile import ContractorProfile


class AssessOrders:
    def __init__(
        self,
        *,
        assessor: LlmAssessor,
        publisher: NotificationPublisher,
        profile: ContractorProfile,
        threshold: int,
        logger: Logger,
    ) -> None:
        self._assessor = assessor
        self._publisher = publisher
        self._profile = profile
        self._threshold = threshold
        self._logger = logger

    async def handle(self, listings: list[Listing]) -> None:
        for listing in listings:
            await self._assess_one(listing)

    async def _assess_one(self, listing: Listing) -> None:
        try:
            assessment = await self._assessor.assess(listing, self._profile)
            decision = decide(assessment, self._threshold)
            if decision.notify:
                await self._publisher.publish(build_notification(listing, assessment))
                self._logger.info(
                    "order_notified",
                    order_id=listing.id,
                    score=assessment.suitability_score,
                )
            else:
                self._logger.info("order_skipped", order_id=listing.id, reason=decision.reason)
        except AssessmentError as exc:
            self._logger.warning("order_failed", order_id=listing.id, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — best-effort: не роняем батч на баге в одном заказе
            self._logger.error("order_unexpected_error", order_id=listing.id, error=repr(exc))
