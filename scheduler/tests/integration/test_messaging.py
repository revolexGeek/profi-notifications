"""Интеграция messaging через in-memory TestRabbitBroker (без реального брокера)."""

from faststream.rabbit import RabbitBroker, TestRabbitBroker

from app.domain.command import ParseCommand
from app.infrastructure.messaging.broker import parse_requests_queue
from app.infrastructure.messaging.mapping import to_parse_request
from app.infrastructure.messaging.scheduling import build_scheduler
from app.infrastructure.messaging.schemas import ParseRequestMessage


async def test_command_publishes_to_parse_requests_as_valid_contract() -> None:
    received: list[ParseRequestMessage] = []
    broker = RabbitBroker()

    @broker.subscriber(parse_requests_queue("parse.requests"))
    async def _consume(message: ParseRequestMessage) -> None:
        received.append(message)

    async with TestRabbitBroker(broker) as br:
        await br.publish(to_parse_request(ParseCommand(request_id="abc")), queue="parse.requests")

    assert received[0].request_id == "abc"
    assert received[0].filter.use_saved_filter is True


async def test_build_scheduler_registers_task() -> None:
    broker = RabbitBroker()

    async def _message() -> dict[str, object]:
        return {"request_id": "x"}

    scheduler = build_scheduler(
        broker, queue="parse.requests", interval_seconds=60, message=_message
    )

    assert scheduler is not None
