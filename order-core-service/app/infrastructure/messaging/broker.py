"""Топология RabbitMQ «мозга».

Вход `parse.results` (от parser-worker) и `assess.results` (от llm) — оба на
default exchange (routing key = имя очереди). Исход: `assess.requests` (в llm,
default exchange) и уведомление в durable direct обменник `notifications`.

`parse.results` — наша очередь: на reject dead-letter'им в свой DLX. А
`assess.results` объявляет llm простой durable-очередью — объявляем идентично
(без своих dead-letter-аргументов), иначе PRECONDITION_FAILED. Ретраи/DLQ для
неё делаем на уровне приложения.
"""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.infrastructure.messaging.publisher import PublisherTransport


def dead_letter_exchange(name: str) -> RabbitExchange:
    return RabbitExchange(name, type=ExchangeType.DIRECT, durable=True)


def notifications_exchange(name: str) -> RabbitExchange:
    return RabbitExchange(name, type=ExchangeType.DIRECT, durable=True)


def build_parse_queue(name: str, *, dlx: str) -> RabbitQueue:
    """Входная очередь parse.results: на reject dead-letter'ит в DLX (rk = имя очереди)."""
    return RabbitQueue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": dlx,
            "x-dead-letter-routing-key": name,
        },
    )


def build_assess_result_queue(name: str) -> RabbitQueue:
    # llm объявляет её простой durable — повторяем один-в-один, без своих аргументов.
    return RabbitQueue(name, durable=True)


def build_dead_letter_queue(name: str) -> RabbitQueue:
    return RabbitQueue(name, durable=True)


def build_assess_request_publisher(broker: RabbitBroker, *, queue: str) -> PublisherTransport:
    # Default exchange, routing key = имя очереди (так читает llm), persist.
    return broker.publisher(queue=queue, persist=True)


def build_notify_publisher(
    broker: RabbitBroker, *, exchange: str, routing_key: str
) -> PublisherTransport:
    return broker.publisher(exchange=notifications_exchange(exchange), routing_key=routing_key)
