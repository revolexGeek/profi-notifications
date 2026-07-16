"""Выходные порты приложения (реализуются в infrastructure).

Домен и сценарий зависят только от этих интерфейсов — конкретные адаптеры
(Groq, RabbitMQ, логгер) подставляются в composition root.
"""

from typing import Protocol

from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from app.domain.result import AssessmentResult


class LlmAssessor(Protocol):
    async def assess(self, listing: Listing, profile: ContractorProfile) -> Assessment: ...


class ResultPublisher(Protocol):
    async def publish(self, result: AssessmentResult) -> None: ...


class Logger(Protocol):
    def debug(self, event: str, **fields: object) -> None: ...
    def info(self, event: str, **fields: object) -> None: ...
    def warning(self, event: str, **fields: object) -> None: ...
    def error(self, event: str, **fields: object) -> None: ...
