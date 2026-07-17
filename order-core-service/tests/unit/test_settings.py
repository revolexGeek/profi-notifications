"""Тесты конфигурации (pydantic-settings, nested-стиль по группам).

Кейсы изолированы от реального .env через chdir во временную папку — иначе
локальный .env разработчика перебивал бы дефолты.
"""

from pathlib import Path

import pytest

from app.infrastructure.config.settings import Settings


def test_applies_contract_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings()

    # Имена очередей/обменников — из контрактов соседей, не выдуманы.
    assert settings.messaging.parse_queue == "parse.results"
    assert settings.messaging.assess_result_queue == "assess.results"
    assert settings.messaging.assess_request_queue == "assess.requests"
    assert settings.messaging.notify_exchange == "notifications"
    assert settings.messaging.notify_routing_key == "notify"
    assert settings.assessment.notify_threshold == 0


def test_reads_env_by_group_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RABBITMQ__HOST", "rabbit")
    monkeypatch.setenv("RABBITMQ__USERNAME", "u")
    monkeypatch.setenv("RABBITMQ__PASSWORD", "p")
    monkeypatch.setenv("POSTGRES__HOST", "pg")
    monkeypatch.setenv("POSTGRES__DB", "brain")
    monkeypatch.setenv("ASSESSMENT__NOTIFY_THRESHOLD", "70")

    settings = Settings()

    assert settings.rabbitmq.url == "amqp://u:p@rabbit:5672/%2F"
    assert settings.postgres.url == "postgresql+asyncpg://postgres:postgres@pg:5432/brain"
    assert settings.assessment.notify_threshold == 70
