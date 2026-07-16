"""Топология RabbitMQ.

Всё на default exchange (как публикует `parser-worker`). Основная очередь на
ошибке dead-letter'ит в `<name>.dlq`; retry-очереди нет — фид самоисцеляется
ре-поллом. Выход — публикация в durable direct обменник `notifications`.
"""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.infrastructure.messaging.publisher import PublisherTransport


def build_input_queue(name: str) -> RabbitQueue:
    return RabbitQueue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": f"{name}.dlq",
        },
    )


def build_dead_letter_queue(input_queue_name: str) -> RabbitQueue:
    return RabbitQueue(f"{input_queue_name}.dlq", durable=True)


def notifications_exchange(name: str) -> RabbitExchange:
    return RabbitExchange(name, type=ExchangeType.DIRECT, durable=True)


def build_notification_publisher(
    broker: RabbitBroker,
    *,
    exchange: str = "notifications",
    routing_key: str = "notify",
) -> PublisherTransport:
    return broker.publisher(
        exchange=notifications_exchange(exchange),
        routing_key=routing_key,
    )
