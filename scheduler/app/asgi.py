"""Точка входа ASGI: `uvicorn app.asgi:app`."""

from app.infrastructure.config.settings import get_settings
from app.main import build_app

app = build_app(get_settings())
