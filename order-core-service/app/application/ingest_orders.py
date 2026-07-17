"""Сценарий приёма заявок: дедуп + инициирование оценки через outbox.

Вся работа — в одной транзакции: новые заявки сохраняются и одновременно
получают событие `assess.requests` в outbox. Повторная доставка батча
идемпотентна — дедуп по `(source, external_id)` и по dedup_key события.
"""

from collections.abc import Callable

from app.application.dto import IncomingOrder
from app.application.ports import Logger, UnitOfWork


class IngestOrders:
    def __init__(self, *, uow_factory: Callable[[], UnitOfWork], logger: Logger) -> None:
        self._uow_factory = uow_factory
        self._logger = logger

    async def handle(self, batch: list[IncomingOrder]) -> None:
        async with self._uow_factory() as uow:
            for order in batch:
                if await uow.orders.insert_new(order):
                    await uow.outbox.add_assessment_request(order)
                    self._logger.info(
                        "order_ingested",
                        source=str(order.source),
                        external_id=order.external_id,
                    )
                else:
                    self._logger.debug(
                        "order_duplicate",
                        source=str(order.source),
                        external_id=order.external_id,
                    )
            await uow.commit()
