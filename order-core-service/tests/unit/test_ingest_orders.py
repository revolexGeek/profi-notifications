"""Тесты сценария приёма заявок: дедуп + outbox(assess) в одной транзакции."""

from app.application.dto import IncomingOrder
from app.application.ingest_orders import IngestOrders
from app.domain.source import Source
from app.domain.status import OrderStatus
from tests.fakes import FakeLogger, FakeUnitOfWorkFactory


def _order(ext: str) -> IncomingOrder:
    return IncomingOrder(source=Source.PROFI, external_id=ext, payload={"id": ext, "title": "t"})


async def test_new_orders_persisted_and_enqueued_for_assessment() -> None:
    uow = FakeUnitOfWorkFactory()

    await IngestOrders(uow_factory=uow, logger=FakeLogger()).handle([_order("1"), _order("2")])

    assert set(uow.order_store) == {(Source.PROFI, "1"), (Source.PROFI, "2")}
    assert [o.external_id for o in uow.outbox.assess] == ["1", "2"]
    assert uow.order_store[(Source.PROFI, "1")].status is OrderStatus.ASSESS_REQUESTED
    assert uow.committed_count == 1


async def test_duplicate_orders_are_deduplicated() -> None:
    uow = FakeUnitOfWorkFactory()
    use_case = IngestOrders(uow_factory=uow, logger=FakeLogger())

    await use_case.handle([_order("1")])
    await use_case.handle([_order("1")])  # повторная доставка того же заказа

    assert len(uow.order_store) == 1
    assert len(uow.outbox.assess) == 1  # второй раз — no-op


async def test_duplicate_within_same_batch_enqueued_once() -> None:
    uow = FakeUnitOfWorkFactory()

    await IngestOrders(uow_factory=uow, logger=FakeLogger()).handle([_order("1"), _order("1")])

    assert len(uow.outbox.assess) == 1
