"""Тесты Groq-адаптера: маппинг вывода и классификация ошибок."""

import groq
import httpx
import pytest
from pydantic import ValidationError

from app.application.errors import PermanentError, TransientError
from app.domain.assessment import Assessment
from app.domain.listing import Listing
from app.domain.profile import ContractorProfile
from app.infrastructure.llm.groq_assessor import GroqAssessor
from app.infrastructure.llm.schemas import LlmAssessmentSchema

PROFILE = ContractorProfile(
    strong_skills=["Python", "FastAPI"],
    unsupported_skills=["PHP"],
    rejected_projects=["дизайн"],
)
_REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")


class FakeStructured:
    def __init__(self, *, result: object = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.last_input: object = None

    async def ainvoke(self, model_input: object) -> object:
        self.last_input = model_input
        if self.error is not None:
            raise self.error
        return self.result


def _status_error(cls: type[groq.APIStatusError], code: int) -> groq.APIStatusError:
    return cls("boom", response=httpx.Response(code, request=_REQUEST), body=None)


def _validation_error() -> ValidationError:
    try:
        LlmAssessmentSchema(summary="s", suitability_score=999)
    except ValidationError as exc:
        return exc
    raise AssertionError("expected ValidationError")


def _listing() -> Listing:
    return Listing(id="1", title="Python backend на FastAPI", description="нужен REST API")


class TestGroqAssessorSuccess:
    async def test_maps_schema_to_domain_assessment(self) -> None:
        schema = LlmAssessmentSchema(
            summary="Бэкенд на FastAPI",
            suitability_score=82,
            matched_strong=["Python", "FastAPI"],
        )
        assessor = GroqAssessor(FakeStructured(result=schema))

        assessment = await assessor.assess(_listing(), PROFILE)

        assert isinstance(assessment, Assessment)
        assert assessment.suitability_score == 82
        assert assessment.matched_strong == ["Python", "FastAPI"]
        assert assessment.summary == "Бэкенд на FastAPI"

    async def test_builds_messages_from_listing_and_profile(self) -> None:
        fake = FakeStructured(result=LlmAssessmentSchema(summary="s", suitability_score=50))
        await GroqAssessor(fake).assess(_listing(), PROFILE)

        messages = fake.last_input
        assert isinstance(messages, list)
        roles = [role for role, _ in messages]
        assert "system" in roles and "human" in roles
        system_text = next(text for role, text in messages if role == "system")
        human_text = next(text for role, text in messages if role == "human")
        assert "Python" in system_text  # профиль попал в контекст
        assert "Python backend на FastAPI" in human_text  # заявка попала в запрос


class TestGroqAssessorErrors:
    async def test_rate_limit_is_transient(self) -> None:
        error = _status_error(groq.RateLimitError, 429)
        with pytest.raises(TransientError):
            await GroqAssessor(FakeStructured(error=error)).assess(_listing(), PROFILE)

    async def test_server_error_is_transient(self) -> None:
        error = _status_error(groq.InternalServerError, 500)
        with pytest.raises(TransientError):
            await GroqAssessor(FakeStructured(error=error)).assess(_listing(), PROFILE)

    async def test_timeout_is_transient(self) -> None:
        with pytest.raises(TransientError):
            await GroqAssessor(FakeStructured(error=groq.APITimeoutError(request=_REQUEST))).assess(
                _listing(), PROFILE
            )

    async def test_generic_5xx_status_is_transient(self) -> None:
        error = _status_error(groq.APIStatusError, 503)
        with pytest.raises(TransientError):
            await GroqAssessor(FakeStructured(error=error)).assess(_listing(), PROFILE)

    async def test_auth_error_is_permanent(self) -> None:
        error = _status_error(groq.AuthenticationError, 401)
        with pytest.raises(PermanentError):
            await GroqAssessor(FakeStructured(error=error)).assess(_listing(), PROFILE)

    async def test_bad_request_is_permanent(self) -> None:
        error = _status_error(groq.BadRequestError, 400)
        with pytest.raises(PermanentError):
            await GroqAssessor(FakeStructured(error=error)).assess(_listing(), PROFILE)

    async def test_invalid_structured_output_is_permanent(self) -> None:
        assessor = GroqAssessor(FakeStructured(error=_validation_error()))
        with pytest.raises(PermanentError):
            await assessor.assess(_listing(), PROFILE)
