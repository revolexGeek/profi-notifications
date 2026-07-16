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
    monkeypatch.setenv("GROQ__API_KEY", "k")
    monkeypatch.setenv("ASSESSMENT__SUITABILITY_THRESHOLD", "75")
    monkeypatch.setenv("MESSAGING__INPUT_QUEUE", "assess.requests")
    monkeypatch.setenv("RABBITMQ__HOST", "rabbit")
    monkeypatch.setenv("RABBITMQ__USERNAME", "u")
    monkeypatch.setenv("RABBITMQ__PASSWORD", "p")

    settings = Settings()

    assert settings.groq.api_key == "k"
    assert settings.assessment.suitability_threshold == 75
    assert settings.messaging.input_queue == "assess.requests"
    assert settings.rabbitmq.url == "amqp://u:p@rabbit:5672/%2F"


def test_applies_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GROQ__API_KEY", "k")

    settings = Settings()

    assert settings.messaging.input_queue == "parse.results"
    assert settings.messaging.notify_exchange == "notifications"
    assert settings.messaging.notify_routing_key == "notify"
    assert settings.assessment.suitability_threshold == 60
    assert settings.groq.model == "llama-3.3-70b-versatile"


def test_requires_groq_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GROQ__API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()
