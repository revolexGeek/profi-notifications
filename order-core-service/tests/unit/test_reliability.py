"""Тесты классификатора сбоев приёма (guard) — на фейках."""

import pytest

from app.application.errors import PermanentError, TransientError
from app.infrastructure.messaging.reliability import DeadLetterPublisher, guard
from app.infrastructure.messaging.schemas import ParseResultMessage
from tests.fakes import FakeLogger

_VALID = {"request_id": "r", "orders": []}
_INVALID = {"no_request_id": True}  # ParseResultMessage требует request_id


class _FakePublisher:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def publish(self, message: dict[str, object]) -> None:
        self.messages.append(message)


async def test_valid_payload_is_handled() -> None:
    seen: list[ParseResultMessage] = []

    async def handle(message: ParseResultMessage) -> None:
        seen.append(message)

    dlq = DeadLetterPublisher(_FakePublisher())
    await guard(
        _VALID, ParseResultMessage.model_validate, handle, dlq=dlq, logger=FakeLogger(), queue="q"
    )

    assert len(seen) == 1


async def test_invalid_payload_is_dead_lettered() -> None:
    publisher = _FakePublisher()

    async def handle(message: ParseResultMessage) -> None:
        raise AssertionError("не должно вызываться на битом payload")

    await guard(
        _INVALID, ParseResultMessage.model_validate, handle,
        dlq=DeadLetterPublisher(publisher), logger=FakeLogger(), queue="q",
    )

    assert publisher.messages[0]["category"] == "invalid-payload"


async def test_permanent_error_is_dead_lettered() -> None:
    publisher = _FakePublisher()

    async def handle(message: ParseResultMessage) -> None:
        raise PermanentError("unknown order")

    await guard(
        _VALID, ParseResultMessage.model_validate, handle,
        dlq=DeadLetterPublisher(publisher), logger=FakeLogger(), queue="q",
    )

    assert publisher.messages[0]["category"] == "permanent"


async def test_transient_error_propagates_for_retry() -> None:
    publisher = _FakePublisher()

    async def handle(message: ParseResultMessage) -> None:
        raise TransientError("db down")

    with pytest.raises(TransientError):
        await guard(
            _VALID, ParseResultMessage.model_validate, handle,
            dlq=DeadLetterPublisher(publisher), logger=FakeLogger(), queue="q",
        )

    assert publisher.messages == []  # временное не dead-letter'им — уйдёт на повтор
