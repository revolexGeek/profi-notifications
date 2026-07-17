"""Тесты конфигурации (pydantic-settings, nested-стиль по группам)."""

from pathlib import Path

import pytest

from app.infrastructure.config.settings import Settings


def test_applies_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # изоляция от .env

    settings = Settings()

    assert settings.scheduler.parse_queue == "parse.requests"  # контракт parser-worker
    assert settings.scheduler.parse_interval_seconds == 300
    assert settings.scheduler.parse_max_pages == 1


def test_reads_env_by_group_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RABBITMQ__HOST", "rabbit")
    monkeypatch.setenv("RABBITMQ__USERNAME", "u")
    monkeypatch.setenv("RABBITMQ__PASSWORD", "p")
    monkeypatch.setenv("SCHEDULER__PARSE_INTERVAL_SECONDS", "60")

    settings = Settings()

    assert settings.rabbitmq.url == "amqp://u:p@rabbit:5672/%2F"
    assert settings.scheduler.parse_interval_seconds == 60
