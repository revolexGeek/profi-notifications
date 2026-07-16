"""Конфигурация сервиса из окружения (pydantic-settings)."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    amqp_url: str = Field("amqp://guest:guest@localhost:5672/", alias="LLM_AMQP_URL")
    input_queue: str = Field("parse.results", alias="LLM_INPUT_QUEUE")
    notify_exchange: str = Field("notifications", alias="LLM_NOTIFY_EXCHANGE")
    notify_routing_key: str = Field("notify", alias="LLM_NOTIFY_ROUTING_KEY")
    prefetch: int = Field(1, alias="LLM_PREFETCH")

    groq_api_key: str = Field(alias="GROQ_API_KEY")
    groq_model: str = Field("llama-3.3-70b-versatile", alias="GROQ_MODEL")
    llm_temperature: float = Field(0.0, alias="LLM_TEMPERATURE")
    llm_timeout: float = Field(30.0, alias="LLM_TIMEOUT")

    suitability_threshold: int = Field(60, alias="SUITABILITY_THRESHOLD")

    http_host: str = Field("0.0.0.0", alias="HTTP_HOST")
    http_port: int = Field(8000, alias="HTTP_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
