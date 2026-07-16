"""Конфигурация сервиса из окружения (pydantic-settings).

Настройки сгруппированы по внешним системам; каждая группа читает свой префикс
`GROUP__`. Верхний `Settings` агрегирует их, `get_settings()` кэширует инстанс.
"""

from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RabbitMQSettings(BaseSettings):
    host: Annotated[str, Field(default="localhost")]
    port: Annotated[int, Field(default=5672)]
    username: Annotated[str, Field(default="guest")]
    password: Annotated[str, Field(default="guest")]
    vhost: Annotated[str, Field(default="/")]

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


class GroqSettings(BaseSettings):
    api_key: Annotated[str, Field(min_length=1)]
    model: Annotated[str, Field(default="llama-3.3-70b-versatile")]
    temperature: Annotated[float, Field(default=0.0, ge=0.0, le=2.0)]
    timeout: Annotated[float, Field(default=30.0, gt=0)]
    max_retries: Annotated[int, Field(default=0, ge=0)]

    model_config = SettingsConfigDict(
        env_prefix="GROQ__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class MessagingSettings(BaseSettings):
    input_queue: Annotated[str, Field(default="parse.results")]
    notify_exchange: Annotated[str, Field(default="notifications")]
    notify_routing_key: Annotated[str, Field(default="notify")]
    prefetch: Annotated[int, Field(default=1, gt=0)]

    model_config = SettingsConfigDict(
        env_prefix="MESSAGING__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AssessmentSettings(BaseSettings):
    suitability_threshold: Annotated[int, Field(default=60, ge=0, le=100)]

    model_config = SettingsConfigDict(
        env_prefix="ASSESSMENT__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    groq: GroqSettings = Field(default_factory=GroqSettings)
    messaging: MessagingSettings = Field(default_factory=MessagingSettings)
    assessment: AssessmentSettings = Field(default_factory=AssessmentSettings)
    log_level: Annotated[str, Field(default="info")]

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
