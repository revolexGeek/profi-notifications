"""Адаптер оценки через Groq (LangChain structured output).

Реализует порт LlmAssessor. Ретраи не держим здесь (max_retries=0 у модели):
транзиентные сбои отдаём наверх как TransientError — заказ вернётся с ре-поллом.
"""

from typing import Protocol

import groq
from pydantic import ValidationError

from app.application.errors import PermanentError, TransientError
from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from app.infrastructure.llm.prompts import Message, build_messages
from app.infrastructure.llm.schemas import LlmAssessmentSchema

_TRANSIENT: tuple[type[Exception], ...] = (
    groq.RateLimitError,
    groq.APIConnectionError,  # включая APITimeoutError
    groq.InternalServerError,
)
_PERMANENT: tuple[type[Exception], ...] = (
    groq.BadRequestError,
    groq.AuthenticationError,
    groq.PermissionDeniedError,
    groq.NotFoundError,
    groq.ConflictError,
    groq.UnprocessableEntityError,
)


class StructuredAssessor(Protocol):
    """Раннабл `ChatGroq.with_structured_output(LlmAssessmentSchema)`."""

    async def ainvoke(self, model_input: list[Message]) -> LlmAssessmentSchema: ...


class GroqAssessor:
    def __init__(self, structured: StructuredAssessor) -> None:
        self._structured = structured

    async def assess(self, listing: Listing, profile: ContractorProfile) -> Assessment:
        messages = build_messages(listing, profile)
        try:
            result = await self._structured.ainvoke(messages)
        except _TRANSIENT as exc:
            raise TransientError(str(exc)) from exc
        except _PERMANENT as exc:
            raise PermanentError(str(exc)) from exc
        except groq.APIStatusError as exc:
            if exc.status_code >= 500:
                raise TransientError(str(exc)) from exc
            raise PermanentError(str(exc)) from exc
        except ValidationError as exc:
            raise PermanentError(f"invalid structured output: {exc}") from exc
        return _to_assessment(result)


def _to_assessment(schema: LlmAssessmentSchema) -> Assessment:
    return Assessment(
        summary=schema.summary,
        suitability_score=schema.suitability_score,
        unsupported_hits=schema.unsupported_hits,
        is_rejected_type=schema.is_rejected_type,
        matched_strong=schema.matched_strong,
        matched_working=schema.matched_working,
        rationale=schema.rationale,
    )
