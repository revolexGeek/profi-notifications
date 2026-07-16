"""Тест composition root: весь граф зависимостей собирается без сети."""

from pathlib import Path

import pytest
from faststream.asgi import AsgiFastStream

from app.infrastructure.config.settings import Settings
from app.main import build_app


def test_build_app_wires_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GROQ__API_KEY", "test-key")

    app = build_app(Settings())

    assert isinstance(app, AsgiFastStream)
