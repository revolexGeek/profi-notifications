"""Конфигурация scheduler из окружения (pydantic-settings, nested-стиль по группам).

`RABBITMQ__*` — брокер; `SCHEDULER__*` — интервал, целевая очередь и параметры
команды парсинга. Дефолт очереди — из контракта `parser-worker` (`parse.requests`).
"""

from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    vhost: str = "/"

    model_config = SettingsConfigDict(
        env_prefix="RABBITMQ__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def url(self) -> str:
        user = quote(self.username, safe="")
        pwd = quote(self.password, safe="")
        vhost_enc = quote(self.vhost, safe="") if self.vhost else "%2F"
        return f"amqp://{user}:{pwd}@{self.host}:{self.port}/{vhost_enc}"


class SchedulerSettings(BaseSettings):
    parse_interval_seconds: Annotated[int, Field(gt=0)] = 300
    parse_queue: str = "parse.requests"  # контракт parser-worker
    parse_max_pages: Annotated[int, Field(gt=0)] = 1
    parse_search_query: str = ""

    model_config = SettingsConfigDict(
        env_prefix="SCHEDULER__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    rabbitmq: RabbitMQSettings = Field(default_factory=lambda: RabbitMQSettings())
    scheduler: SchedulerSettings = Field(default_factory=lambda: SchedulerSettings())
    log_level: str = "info"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        env_nested_delimiter="__",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
