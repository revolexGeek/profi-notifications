"""Composition Root: сборка зависимостей и ASGI-приложения.

Единственное место, где конкретные адаптеры (PostgreSQL, RabbitMQ, логгер)
соединяются со сценариями. `/health` — ping брокера; `/ready` — ping брокера и БД.
После старта объявляется DLQ и запускается фоновое outbox-реле.
"""

from typing import Any

from faststream.asgi import AsgiFastStream, AsgiResponse, get, make_ping_asgi
from faststream.rabbit import Channel, RabbitBroker
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.application.ingest_orders import IngestOrders
from app.application.process_assessment import ProcessAssessment
from app.application.relay_outbox import RelayOutbox
from app.infrastructure.config.settings import Settings
from app.infrastructure.db.engine import create_engine, create_session_factory
from app.infrastructure.db.outbox_dispatch import SqlAlchemyOutboxDispatchFactory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.messaging.broker import (
    build_assess_request_publisher,
    build_assess_result_queue,
    build_dead_letter_queue,
    build_dlq_publisher,
    build_notify_publisher,
    build_parse_queue,
)
from app.infrastructure.messaging.event_publisher import FastStreamEventPublisher
from app.infrastructure.messaging.reliability import DeadLetterPublisher
from app.infrastructure.messaging.subscribers import (
    register_assess_subscriber,
    register_parse_subscriber,
)
from app.infrastructure.observability.logging import JsonLogger
from app.infrastructure.outbox.relay import OutboxRelay


async def _database_ready(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def build_app(settings: Settings) -> AsgiFastStream:
    logger = JsonLogger(service="order-core", level=settings.log_level)
    engine = create_engine(settings.postgres.url)
    session_factory = create_session_factory(engine)
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)

    broker = RabbitBroker(
        settings.rabbitmq.url,
        default_channel=Channel(prefetch_count=settings.messaging.prefetch),
    )

    dlq = DeadLetterPublisher(build_dlq_publisher(broker, queue=settings.messaging.dlq))
    ingest = IngestOrders(uow_factory=uow_factory, logger=logger)
    process = ProcessAssessment(
        uow_factory=uow_factory,
        threshold=settings.assessment.notify_threshold,
        logger=logger,
    )
    register_parse_subscriber(
        broker,
        build_parse_queue(settings.messaging.parse_queue, dlq=settings.messaging.dlq),
        handle=ingest.handle,
        dlq=dlq,
        logger=logger,
    )
    register_assess_subscriber(
        broker,
        build_assess_result_queue(settings.messaging.assess_result_queue),
        handle=process.handle,
        dlq=dlq,
        logger=logger,
    )

    event_publisher = FastStreamEventPublisher(
        assess_request=build_assess_request_publisher(
            broker, queue=settings.messaging.assess_request_queue
        ),
        notify=build_notify_publisher(
            broker,
            exchange=settings.messaging.notify_exchange,
            routing_key=settings.messaging.notify_routing_key,
        ),
    )
    relay = OutboxRelay(
        relay=RelayOutbox(
            dispatch_factory=SqlAlchemyOutboxDispatchFactory(session_factory),
            publisher=event_publisher,
            batch_size=settings.outbox.batch_size,
            logger=logger,
        ),
        interval_ms=settings.outbox.poll_interval_ms,
        logger=logger,
    )

    @get
    async def _readiness(scope: Any) -> AsgiResponse:
        ready = await broker.ping(timeout=5.0) and await _database_ready(engine)
        return AsgiResponse(b"ready" if ready else b"not ready", status_code=200 if ready else 503)

    app = AsgiFastStream(
        broker,
        asgi_routes=[
            ("/health", make_ping_asgi(broker, timeout=5.0)),
            ("/ready", _readiness),
        ],
    )

    @app.after_startup
    async def _startup() -> None:
        await broker.declare_queue(build_dead_letter_queue(settings.messaging.dlq))
        relay.start()

    @app.after_shutdown
    async def _shutdown() -> None:
        await relay.stop()
        await engine.dispose()

    return app
