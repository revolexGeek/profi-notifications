"""Тесты конфигурации (pydantic-settings, nested-стиль по группам).

Все кейсы изолированы от реального .env через chdir во временную папку —
иначе локальный .env разработчика перебивал бы дефолты и required-проверку.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.infrastructure.config.settings import Settings


def test_reads_env_by_group_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM__API_KEY", "k")
    monkeypatch.setenv("ASSESSMENT__SUITABILITY_THRESHOLD", "75")
    monkeypatch.setenv("MESSAGING__INPUT_QUEUE", "custom.in")
    monkeypatch.setenv("RABBITMQ__HOST", "rabbit")
    monkeypatch.setenv("RABBITMQ__USERNAME", "u")
    monkeypatch.setenv("RABBITMQ__PASSWORD", "p")

    settings = Settings()

    assert settings.llm.api_key == "k"
    assert settings.assessment.suitability_threshold == 75
    assert settings.messaging.input_queue == "custom.in"
    assert settings.rabbitmq.url == "amqp://u:p@rabbit:5672/%2F"


def test_applies_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM__API_KEY", "k")

    settings = Settings()

    assert settings.messaging.input_queue == "assess.requests"
    assert settings.messaging.result_queue == "assess.results"
    assert settings.assessment.suitability_threshold == 60
    assert settings.llm.model == "Qwen/Qwen3-32B"
    assert settings.llm.base_url == "https://api.deepinfra.com/v1/openai"


def test_requires_llm_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM__API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()
