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
    build_notification_publisher,
)
from app.infrastructure.messaging.publisher import RabbitNotificationPublisher
from app.infrastructure.messaging.subscriber import register_orders_subscriber
from app.infrastructure.observability.logging import JsonLogger


def _build_assessor(settings: Settings) -> GroqAssessor:
    model = ChatGroq(
        model_name=settings.groq_model,
        temperature=settings.llm_temperature,
        max_retries=0,
        timeout=settings.llm_timeout,
        api_key=SecretStr(settings.groq_api_key),
    )
    structured = cast(StructuredAssessor, model.with_structured_output(LlmAssessmentSchema))
    return GroqAssessor(structured)


def build_app(settings: Settings) -> AsgiFastStream:
    logger = JsonLogger(service="llm", level=settings.log_level)
    broker = RabbitBroker(
        settings.amqp_url,
        default_channel=Channel(prefetch_count=settings.prefetch),
    )
    publisher = build_notification_publisher(
        broker,
        exchange=settings.notify_exchange,
        routing_key=settings.notify_routing_key,
    )
    use_case = AssessOrders(
        assessor=_build_assessor(settings),
        publisher=RabbitNotificationPublisher(publisher),
        profile=DEFAULT_PROFILE,
        threshold=settings.suitability_threshold,
        logger=logger,
    )
    register_orders_subscriber(broker, build_input_queue(settings.input_queue), use_case.handle)

    app = AsgiFastStream(
        broker,
        asgi_routes=[
            ("/health", make_ping_asgi(broker, timeout=5.0)),
            ("/ready", make_ping_asgi(broker, timeout=5.0)),
        ],
    )

    @app.after_startup
    async def _declare_dead_letter_queue() -> None:
        await broker.declare_queue(build_dead_letter_queue(settings.input_queue))

    return app
