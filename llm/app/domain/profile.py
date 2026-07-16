"""Профиль исполнителя — «наши возможности».

Питает две точки: контекст промпта LLM (семантический матч) и доменную
политику решения (жёсткие фильтры/пороги). По бюджету и длительности не
отсекаем — поля информационные.
"""

from pydantic import BaseModel, ConfigDict, Field


class ContractorProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    strong_skills: list[str] = Field(default_factory=list)
    working_skills: list[str] = Field(default_factory=list)
    unsupported_skills: list[str] = Field(default_factory=list)

    project_types: list[str] = Field(default_factory=list)

    infrastructure_experience: list[str] = Field(default_factory=list)
    integrations_experience: list[str] = Field(default_factory=list)

    preferred_projects: list[str] = Field(default_factory=list)
    rejected_projects: list[str] = Field(default_factory=list)

    minimum_budget: int | None = None
    maximum_duration_months: int | None = None
