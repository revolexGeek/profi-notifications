"""Сценарий оценки заказов.

На входе — уже смапленные доменные `Listing`. Обработка best-effort по батчу:
транзиентный сбой (429/5xx/сеть) не роняет остальные заказы, а сам заказ
возвращается наверх для повтора; постоянный сбой логируется и глотается (повтор
не поможет). `handle` возвращает id заказов с транзиентным сбоем — их
переотправляет подписчик в retry-очередь.
"""

from app.application.errors import AssessmentError, TransientError
from app.application.ports import LlmAssessor, Logger, ResultPublisher
from app.domain.decision import decide
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from app.domain.result import build_result


class AssessOrders:
    def __init__(
        self,
        *,
        assessor: LlmAssessor,
        publisher: ResultPublisher,
        profile: ContractorProfile,
        threshold: int,
        logger: Logger,
    ) -> None:
        self._assessor = assessor
        self._publisher = publisher
        self._profile = profile
        self._threshold = threshold
        self._logger = logger

    async def handle(self, listings: list[Listing]) -> list[str]:
        retryable: list[str] = []
        for listing in listings:
            if not await self._assess_one(listing):
                retryable.append(listing.id)
        return retryable

    async def _assess_one(self, listing: Listing) -> bool:
        """`True` — заказ обработан; `False` — транзиентный сбой, нужен повтор."""
        try:
            assessment = await self._assessor.assess(listing, self._profile)
            decision = decide(assessment, self._threshold)
            if decision.notify:
                await self._publisher.publish(build_result(listing, assessment))
                self._logger.info(
                    "result_published",
                    order_id=listing.id,
                    score=assessment.suitability_score,
                )
            else:
                self._logger.info("order_skipped", order_id=listing.id, reason=decision.reason)
        except TransientError as exc:
            self._logger.warning("assessment_retry_scheduled", order_id=listing.id, error=str(exc))
            return False
        except AssessmentError as exc:
            self._logger.warning("order_failed", order_id=listing.id, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — best-effort: не роняем батч на баге в одном заказе
            self._logger.error("order_unexpected_error", order_id=listing.id, error=repr(exc))
        return True
