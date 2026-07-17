"""Топология RabbitMQ «мозга».

Вход `parse.results` (от parser-worker) и `assess.results` (от llm) — оба на
default exchange (routing key = имя очереди). Исход: `assess.requests` (в llm,
default exchange) и уведомление в durable direct обменник `notifications`.

Надёжность приёма — на уровне приложения (см. `reliability.py`): «ядовитые» и
постоянные ошибки публикуются в DLQ (`order.dlq` через default exchange),
временные — NACK/requeue. Единый механизм, т.к. `assess.results` объявляет llm
простой durable-очередью (свои dead-letter-аргументы навесить нельзя).
"""

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange, RabbitQueue

from app.infrastructure.messaging.publisher import PublisherTransport


def notifications_exchange(name: str) -> RabbitExchange:
    return RabbitExchange(name, type=ExchangeType.DIRECT, durable=True)


def build_parse_queue(name: str, *, dlq: str) -> RabbitQueue:
    """Входная очередь parse.results: непойманное на брокере уходит в DLQ (default exchange)."""
    return RabbitQueue(
        name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": dlq,
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


def build_dlq_publisher(broker: RabbitBroker, *, queue: str) -> PublisherTransport:
    # Default exchange, routing key = имя DLQ-очереди; persist — не терять «ядовитое».
    return broker.publisher(queue=queue, persist=True)
