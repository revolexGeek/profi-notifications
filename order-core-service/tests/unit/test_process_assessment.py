"""Тесты сценария обработки вердикта: решение + outbox(notify), идемпотентность."""

import pytest

from app.application.dto import IncomingOrder
from app.application.errors import PermanentError
from app.application.ingest_orders import IngestOrders
from app.application.process_assessment import ProcessAssessment
from app.domain.assessment import AssessmentOutcome
from app.domain.notification import NotificationCommand
from app.domain.source import Source
from app.domain.status import OrderStatus
from tests.fakes import FakeLogger, FakeUnitOfWorkFactory


def _outcome(ext: str, score: int) -> AssessmentOutcome:
    return AssessmentOutcome(
        order_id=ext, suitability_score=score, notification=NotificationCommand(text="t")
    )


async def _ingest(uow: FakeUnitOfWorkFactory, ext: str) -> None:
    await IngestOrders(uow_factory=uow, logger=FakeLogger()).handle(
        [IncomingOrder(source=Source.PROFI, external_id=ext, payload={"id": ext})]
    )


async def test_notifies_and_enqueues_when_above_threshold() -> None:
    uow = FakeUnitOfWorkFactory()
    await _ingest(uow, "1")

    await ProcessAssessment(uow_factory=uow, threshold=0, logger=FakeLogger()).handle(
        _outcome("1", 90)
    )

    order = uow.order_store[(Source.PROFI, "1")]
    assert order.status is OrderStatus.NOTIFY_REQUESTED
    assert order.suitability_score == 90
    assert len(uow.outbox.notify) == 1


async def test_marks_no_notify_below_threshold() -> None:
    uow = FakeUnitOfWorkFactory()
    await _ingest(uow, "1")

    await ProcessAssessment(uow_factory=uow, threshold=80, logger=FakeLogger()).handle(
        _outcome("1", 50)
    )

    assert uow.order_store[(Source.PROFI, "1")].status is OrderStatus.NO_NOTIFY
    assert uow.outbox.notify == []


async def test_duplicate_result_is_idempotent() -> None:
    uow = FakeUnitOfWorkFactory()
    await _ingest(uow, "1")
    use_case = ProcessAssessment(uow_factory=uow, threshold=0, logger=FakeLogger())

    await use_case.handle(_outcome("1", 90))
    await use_case.handle(_outcome("1", 90))  # повторная доставка вердикта

    assert len(uow.outbox.notify) == 1  # второй раз — no-op (статус уже NOTIFY_REQUESTED)


async def test_unknown_order_raises_permanent() -> None:
    uow = FakeUnitOfWorkFactory()

    with pytest.raises(PermanentError):
        await ProcessAssessment(uow_factory=uow, threshold=0, logger=FakeLogger()).handle(
            _outcome("404", 90)
        )
