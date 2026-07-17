"""Конфигурация сервиса из окружения (pydantic-settings).

Настройки сгруппированы по внешним системам; каждая группа читает свой префикс
`GROUP__`. Верхний `Settings` агрегирует их, `get_settings()` кэширует инстанс.

Дефолты messaging заданы **по контрактам соседних сервисов** (parser-worker, llm,
notifications) — имена очередей/обменников не выдуманы. Свои элементы надёжности
приёма (`order.dlx`/`order.dlq`/`order.retry`) вынесены под префикс `order.`.
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


class PostgresSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    username: str = "postgres"
    password: str = "postgres"
    db: str = "order_core"

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def url(self) -> str:
        user = quote(self.username, safe="")
        pwd = quote(self.password, safe="")
        return f"postgresql+asyncpg://{user}:{pwd}@{self.host}:{self.port}/{self.db}"


class MessagingSettings(BaseSettings):
    # Входящие (потребляем). Default exchange, routing key = имя очереди.
    parse_queue: str = "parse.results"  # от parser-worker
    assess_result_queue: str = "assess.results"  # от llm

    # Исходящие (публикуем через outbox-реле).
    assess_request_queue: str = "assess.requests"  # в llm (default exchange)
    notify_exchange: str = "notifications"  # в notifications (direct, durable)
    notify_routing_key: str = "notify"

    # Надёжность приёма — свои обменники/очереди (namespaced `order.`).
    dlx: str = "order.dlx"
    dlq: str = "order.dlq"
    retry_exchange: str = "order.retry"
    retry_queue: str = "order.retry"

    prefetch: Annotated[int, Field(gt=0)] = 10
    retry_delay_ms: Annotated[int, Field(gt=0)] = 30_000
    max_attempts: Annotated[int, Field(gt=0)] = 5

    model_config = SettingsConfigDict(
        env_prefix="MESSAGING__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AssessmentSettings(BaseSettings):
    # Порог «мозга» поверх фильтра llm. 0 = доверяем llm, точка решения сохранена.
    notify_threshold: Annotated[int, Field(ge=0, le=100)] = 0

    model_config = SettingsConfigDict(
        env_prefix="ASSESSMENT__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class OutboxSettings(BaseSettings):
    poll_interval_ms: Annotated[int, Field(gt=0)] = 1000
    batch_size: Annotated[int, Field(gt=0)] = 100
    max_attempts: Annotated[int, Field(gt=0)] = 10

    model_config = SettingsConfigDict(
        env_prefix="OUTBOX__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    rabbitmq: RabbitMQSettings = Field(default_factory=lambda: RabbitMQSettings())
    postgres: PostgresSettings = Field(default_factory=lambda: PostgresSettings())
    messaging: MessagingSettings = Field(default_factory=lambda: MessagingSettings())
    assessment: AssessmentSettings = Field(default_factory=lambda: AssessmentSettings())
    outbox: OutboxSettings = Field(default_factory=lambda: OutboxSettings())
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
