"""Адаптер оценки через OpenAI-совместимый эндпоинт (LangChain structured output).

Реализует порт LlmAssessor. Транзиентные сбои (429/5xx/сеть) отдаём наверх как
TransientError, постоянные — как PermanentError. Ретраи короткого rate limit
держит сам клиент (`LLM__MAX_RETRIES`), устойчивые — подписчик (retry-очередь).
"""

from typing import Protocol

import openai
from pydantic import ValidationError

from app.application.errors import PermanentError, TransientError
from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from app.infrastructure.llm.prompts import Message, build_messages
from app.infrastructure.llm.schemas import LlmAssessmentSchema

_TRANSIENT: tuple[type[Exception], ...] = (
    openai.RateLimitError,
    openai.APIConnectionError,  # включая APITimeoutError
    openai.InternalServerError,
)
_PERMANENT: tuple[type[Exception], ...] = (
    openai.BadRequestError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.ConflictError,
    openai.UnprocessableEntityError,
)


class StructuredAssessor(Protocol):
    """Раннабл `ChatOpenAI.with_structured_output(LlmAssessmentSchema)`."""

    async def ainvoke(self, model_input: list[Message]) -> LlmAssessmentSchema: ...


class OpenAiAssessor:
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
        except openai.APIStatusError as exc:
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
