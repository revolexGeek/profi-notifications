"""Конфигурация сервиса из окружения (pydantic-settings).

Настройки сгруппированы по внешним системам; каждая группа читает свой префикс
`GROUP__`. Верхний `Settings` агрегирует их, `get_settings()` кэширует инстанс.

Дефолты держим в ассайн-форме, а вложенные группы подставляем через `lambda`,
чтобы конфиг был чистым и для mypy, и для Pyright (он не знает про env-источники
BaseSettings). Обязательный `LLM__API_KEY` смоделирован как непустая строка:
дефолт `""` валидируется и падает, если переменная не задана.
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


class LlmSettings(BaseSettings):
    """OpenAI-совместимый эндпоинт (по умолчанию DeepInfra)."""

    api_key: Annotated[str, Field(min_length=1, validate_default=True)] = ""
    model: str = "Qwen/Qwen3-32B"
    base_url: str = "https://api.deepinfra.com/v1/openai"
    temperature: Annotated[float, Field(ge=0.0, le=2.0)] = 0.0
    max_tokens: Annotated[int, Field(gt=0)] = 2048
    timeout: Annotated[float, Field(gt=0)] = 60.0
    max_retries: Annotated[int, Field(ge=0)] = 3
    service_tier: str = "flex"
    # Qwen3 и др. reasoning-модели: выключаем «мышление» (иначе <think> съедает
    # токены до JSON и ответ обрезается). Для задачи-классификации не нужно.
    enable_thinking: bool = False

    model_config = SettingsConfigDict(
        env_prefix="LLM__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class MessagingSettings(BaseSettings):
    input_queue: str = "assess.requests"
    result_queue: str = "assess.results"
    prefetch: Annotated[int, Field(gt=0)] = 1
    retry_ttl_ms: Annotated[int, Field(gt=0)] = 15000

    model_config = SettingsConfigDict(
        env_prefix="MESSAGING__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AssessmentSettings(BaseSettings):
    suitability_threshold: Annotated[int, Field(ge=0, le=100)] = 60

    model_config = SettingsConfigDict(
        env_prefix="ASSESSMENT__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class Settings(BaseSettings):
    rabbitmq: RabbitMQSettings = Field(default_factory=lambda: RabbitMQSettings())
    llm: LlmSettings = Field(default_factory=lambda: LlmSettings())
    messaging: MessagingSettings = Field(default_factory=lambda: MessagingSettings())
    assessment: AssessmentSettings = Field(default_factory=lambda: AssessmentSettings())
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
