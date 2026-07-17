"""Composition Root: сборка зависимостей и ASGI-приложения.

Единственное место, где конкретные адаптеры (Groq, RabbitMQ, логгер)
соединяются со сценарием. Health/readiness — ping брокера.
"""

from typing import cast

from faststream.asgi import AsgiFastStream, make_ping_asgi
from faststream.rabbit import Channel, RabbitBroker
from langchain_groq import ChatGroq
from pydantic import SecretStr

from app.application.assess_orders import AssessOrders
from app.infrastructure.config.profile import DEFAULT_PROFILE
from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.groq_assessor import GroqAssessor, StructuredAssessor
from app.infrastructure.llm.schemas import LlmAssessmentSchema
from app.infrastructure.messaging.broker import (
    build_dead_letter_queue,
    build_input_queue,
    build_result_publisher,
    build_result_queue,
    build_retry_publisher,
    build_retry_queue,
)
from app.infrastructure.messaging.publisher import RabbitResultPublisher
from app.infrastructure.messaging.subscriber import register_orders_subscriber
from app.infrastructure.observability.logging import JsonLogger


def _build_assessor(settings: Settings) -> GroqAssessor:
    # langchain-плагин mypy требует field-name `model_name`, Pyright и публичный API — `model`.
    model = ChatGroq(  # type: ignore[call-arg]
        model=settings.groq.model,
        temperature=settings.groq.temperature,
        max_retries=settings.groq.max_retries,
        timeout=settings.groq.timeout,
        api_key=SecretStr(settings.groq.api_key),
    )
    structured = cast(StructuredAssessor, model.with_structured_output(LlmAssessmentSchema))
    return GroqAssessor(structured)


def build_app(settings: Settings) -> AsgiFastStream:
    logger = JsonLogger(service="llm", level=settings.log_level)
    broker = RabbitBroker(
        settings.rabbitmq.url,
        default_channel=Channel(prefetch_count=settings.messaging.prefetch),
    )
    publisher = build_result_publisher(broker, queue=settings.messaging.result_queue)
    retry_publisher = build_retry_publisher(broker, input_queue=settings.messaging.input_queue)
    use_case = AssessOrders(
        assessor=_build_assessor(settings),
        publisher=RabbitResultPublisher(publisher),
        profile=DEFAULT_PROFILE,
        threshold=settings.assessment.suitability_threshold,
        logger=logger,
    )
    register_orders_subscriber(
        broker,
        build_input_queue(settings.messaging.input_queue),
        use_case.handle,
        retry_publisher=retry_publisher,
    )

    app = AsgiFastStream(
        broker,
        asgi_routes=[
            ("/health", make_ping_asgi(broker, timeout=5.0)),
            ("/ready", make_ping_asgi(broker, timeout=5.0)),
        ],
    )

    @app.after_startup
    async def _declare_queues() -> None:
        await broker.declare_queue(build_dead_letter_queue(settings.messaging.input_queue))
        await broker.declare_queue(
            build_retry_queue(
                settings.messaging.input_queue, ttl_ms=settings.messaging.retry_ttl_ms
            )
        )
        await broker.declare_queue(build_result_queue(settings.messaging.result_queue))

    return app
