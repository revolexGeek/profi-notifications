"""Топология RabbitMQ.

Всё на default exchange (routing key = имя очереди). Вход `assess.requests`
(от «мозга») на ошибке dead-letter'ит в `<name>.dlq`; retry-очереди нет.
Выход — результат оценки в durable-очередь `assess.results` (persist), её
читает «мозг».
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


def build_result_queue(name: str) -> RabbitQueue:
    return RabbitQueue(name, durable=True)


def build_result_publisher(broker: RabbitBroker, *, queue: str) -> PublisherTransport:
    return broker.publisher(queue=queue, persist=True)
