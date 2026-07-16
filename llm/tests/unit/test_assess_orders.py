"""Тесты сценария оценки заказов (best-effort по батчу)."""

from app.application.assess_orders import AssessOrders
from app.application.errors import PermanentError, TransientError
from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from tests.fakes import FakeAssessor, FakeLogger, FakePublisher

PROFILE = ContractorProfile(strong_skills=["Python"])


def _listing(id_: str) -> Listing:
    return Listing(id=id_, title=f"t{id_}", description="d")


def _use_case(
    assessor: FakeAssessor, publisher: FakePublisher, logger: FakeLogger, threshold: int = 60
) -> AssessOrders:
    return AssessOrders(
        assessor=assessor,
        publisher=publisher,
        profile=PROFILE,
        threshold=threshold,
        logger=logger,
    )


class TestAssessOrders:
    async def test_publishes_when_suitable(self) -> None:
        assessor = FakeAssessor({"1": Assessment(summary="s", suitability_score=90)})
        publisher, logger = FakePublisher(), FakeLogger()

        await _use_case(assessor, publisher, logger).handle([_listing("1")])

        assert len(publisher.published) == 1
        assert publisher.published[0].order_id == "1"
        assert publisher.published[0].suitability_score == 90
        assert logger.events_of("result_published")

    async def test_does_not_publish_when_not_suitable(self) -> None:
        assessor = FakeAssessor({"1": Assessment(summary="s", suitability_score=10)})
        publisher, logger = FakePublisher(), FakeLogger()

        await _use_case(assessor, publisher, logger).handle([_listing("1")])

        assert publisher.published == []
        assert logger.events_of("order_skipped")

    async def test_best_effort_continues_after_transient_error(self) -> None:
        assessor = FakeAssessor(
            {
                "1": TransientError("429"),
                "2": Assessment(summary="s", suitability_score=90),
            }
        )
        publisher, logger = FakePublisher(), FakeLogger()

        await _use_case(assessor, publisher, logger).handle([_listing("1"), _listing("2")])

        assert len(publisher.published) == 1  # заказ 2 всё равно обработан
        assert assessor.calls == ["1", "2"]
        assert logger.events_of("order_failed")

    async def test_permanent_error_is_swallowed(self) -> None:
        assessor = FakeAssessor({"1": PermanentError("400")})
        publisher, logger = FakePublisher(), FakeLogger()

        await _use_case(assessor, publisher, logger).handle([_listing("1")])

        assert publisher.published == []
        assert logger.events_of("order_failed")

    async def test_publish_failure_does_not_break_batch(self) -> None:
        assessor = FakeAssessor(
            {
                "1": Assessment(summary="s", suitability_score=90),
                "2": Assessment(summary="s", suitability_score=90),
            }
        )
        publisher = FakePublisher(error=TransientError("broker down"))
        logger = FakeLogger()

        await _use_case(assessor, publisher, logger).handle([_listing("1"), _listing("2")])

        assert assessor.calls == ["1", "2"]  # батч дошёл до конца, исключение не всплыло
        assert publisher.published == []
