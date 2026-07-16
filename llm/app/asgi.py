"""Точка входа: `faststream run app.asgi:app`."""

from app.infrastructure.config.settings import Settings
from app.main import build_app

app = build_app(Settings())
