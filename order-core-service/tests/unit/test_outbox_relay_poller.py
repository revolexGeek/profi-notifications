"""Тесты фонового поллера outbox-реле (тик, устойчивость к ошибкам, остановка)."""

import asyncio

from app.infrastructure.outbox.relay import OutboxRelay
from tests.fakes import FakeLogger


class _ScriptedRelay:
    """run_once: 1 (есть работа) → бросает (ошибка) → 0 (простой, сигналит готовность)."""

    def __init__(self) -> None:
        self.calls = 0
        self.reached_idle = asyncio.Event()

    async def run_once(self) -> int:
        self.calls += 1
        if self.calls == 1:
            return 1
        if self.calls == 2:
            raise RuntimeError("boom")
        self.reached_idle.set()
        return 0


async def test_poller_ticks_survives_errors_and_stops() -> None:
    relay = _ScriptedRelay()
    logger = FakeLogger()
    poller = OutboxRelay(relay=relay, interval_ms=1, logger=logger)  # type: ignore[arg-type]

    poller.start()
    await asyncio.wait_for(relay.reached_idle.wait(), timeout=2)
    await poller.stop()

    assert relay.calls >= 3
    assert logger.events_of("outbox_relay_error")  # ошибка залогирована, цикл выжил


async def test_stop_without_start_is_safe() -> None:
    poller = OutboxRelay(relay=_ScriptedRelay(), interval_ms=1, logger=FakeLogger())  # type: ignore[arg-type]

    await poller.stop()  # не должно падать
