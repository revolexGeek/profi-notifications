"""Тесты конфигурации (pydantic-settings)."""

import pytest
from pydantic import ValidationError

from app.infrastructure.config.settings import Settings


def test_reads_env_by_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("SUITABILITY_THRESHOLD", "75")
    monkeypatch.setenv("LLM_INPUT_QUEUE", "assess.requests")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key == "k"
    assert settings.suitability_threshold == 75
    assert settings.input_queue == "assess.requests"


def test_applies_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "k")

    settings = Settings(_env_file=None)

    assert settings.input_queue == "parse.results"
    assert settings.notify_exchange == "notifications"
    assert settings.notify_routing_key == "notify"
    assert settings.suitability_threshold == 60


def test_requires_groq_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
