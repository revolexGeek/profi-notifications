"""Тесты топологии: основная очередь dead-letter'ит в DLQ через default exchange."""

from app.infrastructure.messaging.broker import build_dead_letter_queue, build_input_queue


def test_input_queue_dead_letters_to_dlq() -> None:
    queue = build_input_queue("parse.results")

    assert queue.name == "parse.results"
    assert queue.arguments is not None
    assert queue.arguments["x-dead-letter-exchange"] == ""
    assert queue.arguments["x-dead-letter-routing-key"] == "parse.results.dlq"


def test_dead_letter_queue_name() -> None:
    assert build_dead_letter_queue("parse.results").name == "parse.results.dlq"
