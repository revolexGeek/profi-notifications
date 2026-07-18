"""Топология RabbitMQ.

Всё на default exchange (routing key = имя очереди). Вход `assess.requests`
(от «мозга»). Транзиентные сбои оценки (429/5xx/сеть) уходят в retry-очередь
`<name>.retry` (TTL), которая dead-letter'ит заказ обратно во вход — отложенный
повтор, заказ не теряется. Нераспарсиваемый конверт reject'ится в `<name>.dlq`.
Выход — результат оценки в durable-очередь `assess.results` (persist).
"""

from faststream.rabbit import RabbitBroker, RabbitQueue

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


def build_retry_queue(input_queue_name: str, *, ttl_ms: int) -> RabbitQueue:
    """Держит заказ `ttl_ms`, затем dead-letter'ит обратно во входную очередь."""
    return RabbitQueue(
        f"{input_queue_name}.retry",
        durable=True,
        arguments={
            "x-message-ttl": ttl_ms,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": input_queue_name,
        },
    )


def build_result_queue(name: str) -> RabbitQueue:
    return RabbitQueue(name, durable=True)


def build_result_publisher(broker: RabbitBroker, *, queue: str) -> PublisherTransport:
    return broker.publisher(queue=queue, persist=True)


def build_retry_publisher(broker: RabbitBroker, *, input_queue: str) -> PublisherTransport:
    return broker.publisher(queue=f"{input_queue}.retry", persist=True)
