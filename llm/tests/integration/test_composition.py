"""Тест composition root: весь граф зависимостей собирается без сети."""

import pytest
from faststream.asgi import AsgiFastStream

from app.infrastructure.config.settings import Settings
from app.main import build_app


def test_build_app_wires_service(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ__API_KEY", "test-key")

    app = build_app(Settings())

    assert isinstance(app, AsgiFastStream)
