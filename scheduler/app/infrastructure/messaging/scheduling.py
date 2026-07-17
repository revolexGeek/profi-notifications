"""Планирование публикаций через taskiq-faststream (без Taskiq worker).

`BrokerWrapper` оборачивает FastStream-брокер; `StreamScheduler` по расписанию
сам вызывает `message`-callable и публикует результат в очередь (без отдельного
worker'а). `message` — async-фабрика: каждый тик отдаёт свежий payload команды.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from faststream.rabbit import RabbitBroker
from taskiq.schedule_sources import LabelScheduleSource
from taskiq_faststream import BrokerWrapper, StreamScheduler

MessageFactory = Callable[[], Awaitable[dict[str, Any]]]


def build_scheduler(
    broker: RabbitBroker,
    *,
    queue: str,
    interval_seconds: int,
    message: MessageFactory,
) -> StreamScheduler:
    taskiq_broker = BrokerWrapper(broker)
    # `interval` taskiq core поддерживает в рантайме, но TypedDict taskiq-faststream его
    # не типизирует — аннотируем как list[Any], чтобы mypy не ругался на «лишние» ключи.
    schedule: list[Any] = [{"interval": interval_seconds, "schedule_id": "parse-orders"}]
    taskiq_broker.task(message=message, queue=queue, schedule=schedule)
    return StreamScheduler(taskiq_broker, sources=[LabelScheduleSource(taskiq_broker)])
