"""Фоновый поллер outbox-реле: тикает, публикует накопленное, не падает от ошибок.

Есть работа — сразу берёт следующий батч; пусто — ждёт интервал. Стартует в
composition root после подключения брокера, останавливается при shutdown.
"""

import asyncio
import contextlib

from app.application.ports import Logger
from app.application.relay_outbox import RelayOutbox


class OutboxRelay:
    def __init__(self, *, relay: RelayOutbox, interval_ms: int, logger: Logger) -> None:
        self._relay = relay
        self._interval = interval_ms / 1000
        self._logger = logger
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run_forever(self) -> None:
        while True:
            try:
                published = await self._relay.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # реле не должно падать на разовой ошибке
                self._logger.error("outbox_relay_error", error=repr(exc))
                published = 0
            await asyncio.sleep(0 if published > 0 else self._interval)
