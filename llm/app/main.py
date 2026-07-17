"""Composition Root: сборка зависимостей и ASGI-приложения.

Единственное место, где конкретные адаптеры (Groq, RabbitMQ, логгер)
соединяются со сценарием. Health/readiness — ping брокера.
"""

from typing import cast

from faststream.asgi import AsgiFastStream, make_ping_asgi
from faststream.rabbit import Channel, RabbitBroker
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.application.assess_orders import AssessOrders
from app.infrastructure.config.profile import DEFAULT_PROFILE
from app.infrastructure.config.settings import Settings
from app.infrastructure.llm.openai_assessor import OpenAiAssessor, StructuredAssessor
from app.infrastructure.llm.schemas import LlmAssessmentSchema
from app.infrastructure.messaging.broker import (
    build_dead_letter_queue,
    build_input_queue,
    build_result_publisher,
    build_result_queue,
)
from app.infrastructure.messaging.publisher import RabbitResultPublisher
from app.infrastructure.messaging.subscriber import register_orders_subscriber
from app.infrastructure.observability.logging import JsonLogger


def _build_assessor(settings: Settings) -> OpenAiAssessor:
    model = ChatOpenAI(
        model=settings.llm.model,
        base_url=settings.llm.base_url,
        api_key=SecretStr(settings.llm.api_key),
        temperature=settings.llm.temperature,
        max_tokens=settings.llm.max_tokens,
        timeout=settings.llm.timeout,
        max_retries=settings.llm.max_retries,
        extra_body={
            "service_tier": settings.llm.service_tier,
            "chat_template_kwargs": {"enable_thinking": settings.llm.enable_thinking},
        },
    )
    structured = cast(StructuredAssessor, model.with_structured_output(LlmAssessmentSchema))
    return OpenAiAssessor(structured)


def build_app(settings: Settings) -> AsgiFastStream:
    logger = JsonLogger(service="llm", level=settings.log_level)
    broker = RabbitBroker(
        settings.rabbitmq.url,
        default_channel=Channel(prefetch_count=settings.messaging.prefetch),
    )
    publisher = build_result_publisher(broker, queue=settings.messaging.result_queue)
    use_case = AssessOrders(
        assessor=_build_assessor(settings),
        publisher=RabbitResultPublisher(publisher),
        profile=DEFAULT_PROFILE,
        threshold=settings.assessment.suitability_threshold,
        logger=logger,
    )
    register_orders_subscriber(
        broker, build_input_queue(settings.messaging.input_queue), use_case.handle
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
        await broker.declare_queue(build_result_queue(settings.messaging.result_queue))

    return app
