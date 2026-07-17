"""Тесты топологии: вход, retry-очередь (TTL → назад), DLQ, durable-выход."""

from app.infrastructure.messaging.broker import (
    build_dead_letter_queue,
    build_input_queue,
    build_result_queue,
    build_retry_queue,
)


def test_input_queue_dead_letters_to_dlq() -> None:
    queue = build_input_queue("assess.requests")

    assert queue.name == "assess.requests"
    assert queue.arguments is not None
    assert queue.arguments["x-dead-letter-exchange"] == ""
    assert queue.arguments["x-dead-letter-routing-key"] == "assess.requests.dlq"


def test_dead_letter_queue_name() -> None:
    assert build_dead_letter_queue("assess.requests").name == "assess.requests.dlq"


def test_retry_queue_ttl_and_dead_letters_back_to_input() -> None:
    queue = build_retry_queue("assess.requests", ttl_ms=15000)

    assert queue.name == "assess.requests.retry"
    assert queue.arguments is not None
    assert queue.arguments["x-message-ttl"] == 15000
    assert queue.arguments["x-dead-letter-routing-key"] == "assess.requests"


def test_result_queue_is_durable() -> None:
    queue = build_result_queue("assess.results")

    assert queue.name == "assess.results"
    assert queue.durable is True
