"""Подписчик parse.results — Humble Object.

Только десериализация, маппинг заказов в доменные Listing и делегирование
обработчику. Бизнес-логики здесь нет. REJECT_ON_ERROR: нераспарсиваемый
конверт уходит в DLQ, а не крутится в hot-loop.
"""

from collections.abc import Awaitable, Callable

from faststream import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.domain.listing import Listing
from app.infrastructure.messaging.mapping import order_to_listing
from app.infrastructure.messaging.schemas import ParseResultMessage

OrdersHandler = Callable[[list[Listing]], Awaitable[None]]


def register_orders_subscriber(
    broker: RabbitBroker, queue: RabbitQueue, handle: OrdersHandler
) -> None:
    @broker.subscriber(queue, ack_policy=AckPolicy.REJECT_ON_ERROR)
    async def _on_parse_results(message: ParseResultMessage) -> None:
        await handle([order_to_listing(order) for order in message.orders])
