"""Подписчик assess.requests — Humble Object.

Десериализация, маппинг заказов в доменные Listing, делегирование сценарию.
Заказы с транзиентным сбоем сценарий возвращает — подписчик переотправляет их в
retry-очередь (отложенный повтор, заказ не теряется). REJECT_ON_ERROR:
нераспарсиваемый конверт уходит в DLQ, а не крутится в hot-loop.
"""

from collections.abc import Awaitable, Callable

from faststream import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.domain.listing import Listing
from app.infrastructure.messaging.mapping import order_to_listing
from app.infrastructure.messaging.publisher import PublisherTransport
from app.infrastructure.messaging.schemas import ParseResultMessage

OrdersHandler = Callable[[list[Listing]], Awaitable[list[str]]]


def register_orders_subscriber(
    broker: RabbitBroker,
    queue: RabbitQueue,
    handle: OrdersHandler,
    *,
    retry_publisher: PublisherTransport,
) -> None:
    @broker.subscriber(queue, ack_policy=AckPolicy.REJECT_ON_ERROR)
    async def _on_assess_requests(message: ParseResultMessage) -> None:
        retryable = set(await handle([order_to_listing(order) for order in message.orders]))
        if retryable:
            failed = [order for order in message.orders if order.id in retryable]
            await retry_publisher.publish(
                message.model_copy(update={"orders": failed}).model_dump()
            )
