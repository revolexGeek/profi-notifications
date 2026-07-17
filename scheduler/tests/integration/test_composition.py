"""Smoke-тест composition root: build_app собирает приложение (ленивое, без коннекта)."""

from pathlib import Path

import pytest

from app.infrastructure.config.settings import Settings
from app.main import build_app


def test_build_app_wires_application(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)  # изоляция от .env

    app = build_app(Settings())

    assert app is not None
    assert app.broker is not None
