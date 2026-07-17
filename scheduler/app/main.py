"""Composition Root: сборка scheduler + ASGI (health/ready/metrics).

«Пустой» брокер (только паблиш) + taskiq-faststream StreamScheduler, запущенный
фоново в after_startup через `run_scheduler` — **без отдельного Taskiq worker**.
`/health` — liveness, `/ready` — пинг брокера, `/metrics` — счётчики публикаций.
"""

import asyncio
import contextlib
from typing import Any

from faststream.asgi import AsgiFastStream, AsgiResponse, get, make_ping_asgi
from faststream.rabbit import RabbitBroker
from taskiq.cli.scheduler.args import SchedulerArgs
from taskiq.cli.scheduler.run import run_scheduler

from app.application.build_parse_command import BuildParseCommand
from app.infrastructure.config.settings import Settings
from app.infrastructure.ids import UuidGenerator
from app.infrastructure.messaging.broker import parse_requests_queue
from app.infrastructure.messaging.mapping import to_parse_request
from app.infrastructure.messaging.scheduling import build_scheduler
from app.infrastructure.observability.logging import JsonLogger
from app.infrastructure.observability.metrics import PrometheusMetrics

_METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def build_app(settings: Settings) -> AsgiFastStream:
    logger = JsonLogger(service="scheduler", level=settings.log_level)
    metrics = PrometheusMetrics()
    broker = RabbitBroker(settings.rabbitmq.url)

    use_case = BuildParseCommand(
        id_generator=UuidGenerator(),
        search_query=settings.scheduler.parse_search_query,
        max_pages=settings.scheduler.parse_max_pages,
        logger=logger,
        metrics=metrics,
    )

    async def _next_parse_request() -> dict[str, Any]:
        return to_parse_request(use_case.build())

    scheduler = build_scheduler(
        broker,
        queue=settings.scheduler.parse_queue,
        interval_seconds=settings.scheduler.parse_interval_seconds,
        message=_next_parse_request,
    )

    @get
    async def _health(scope: Any) -> AsgiResponse:
        return AsgiResponse(b"ok", status_code=200)

    @get
    async def _metrics(scope: Any) -> AsgiResponse:
        return AsgiResponse(
            metrics.render().encode(),
            status_code=200,
            headers={"content-type": _METRICS_CONTENT_TYPE},
        )

    app = AsgiFastStream(
        broker,
        asgi_routes=[
            ("/health", _health),
            ("/ready", make_ping_asgi(broker, timeout=5.0)),
            ("/metrics", _metrics),
        ],
    )

    tasks: dict[str, asyncio.Task[None]] = {}

    @app.after_startup
    async def _startup() -> None:
        await broker.declare_queue(parse_requests_queue(settings.scheduler.parse_queue))
        args = SchedulerArgs(scheduler=scheduler, modules=[], configure_logging=False)
        tasks["scheduler"] = asyncio.create_task(run_scheduler(args))
        logger.info(
            "scheduler_started", interval_seconds=settings.scheduler.parse_interval_seconds
        )

    @app.after_shutdown
    async def _shutdown() -> None:
        task = tasks.get("scheduler")
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    return app
