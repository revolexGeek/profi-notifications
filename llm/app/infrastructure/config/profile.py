"""Профиль исполнителя по умолчанию.

Значения — пример для публичного репозитория; при необходимости приватности
вынеси в файл по PROFILE_PATH и добавь его в .gitignore.
"""

from app.domain.profile import ContractorProfile

DEFAULT_PROFILE = ContractorProfile(
    strong_skills=[
        "Python",
        "FastAPI",
        "PostgreSQL",
        "SQLAlchemy",
        "Redis",
        "RabbitMQ",
        "Docker",
        "LLM",
        "RAG",
    ],
    working_skills=[
        "ClickHouse",
        "Kafka",
        "Kubernetes",
        "Data Science",
        "Power BI",
    ],
    unsupported_skills=[
        "1C",
        "Bitrix frontend",
        "iOS",
        "Android",
        "PHP",
    ],
    project_types=[
        "backend",
        "devops",
        "machine_learning",
        "llm",
        "automation",
    ],
    infrastructure_experience=[
        "Docker Compose",
        "Docker Swarm",
        "Nginx",
        "Traefik",
        "Prometheus",
        "Grafana",
    ],
    integrations_experience=[
        "Telegram",
        "Bitrix24",
        "LLM API",
        "payment APIs",
    ],
    preferred_projects=[
        "Python backend",
        "LLM integrations",
        "RAG",
        "automation",
        "data processing",
    ],
    rejected_projects=[
        "учебные работы",
        "чистый frontend",
        "дизайн",
        "накрутка",
    ],
    minimum_budget=None,
    maximum_duration_months=None,
)
